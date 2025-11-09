"""
Packager Agent for the LangGraph travel planning workflow.

This agent is responsible for building optimized day-by-day schedules from
POI candidates, including time blocks, travel times, and generating output
artifacts (booking links, maps, calendar exports).
"""

from langchain_core.messages import SystemMessage, HumanMessage
from .state import TripState, Day, TimeBlock
from .llm_config import llm_provider
from backend.tools.distance import calculate_distance
from backend.tools.links import build_flight_link, build_hotel_link
from backend.tools.geo import make_geojson
from backend.tools.calendar import export_calendar
import json
import logging
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

PACKAGER_SYSTEM_PROMPT = """You are a travel itinerary builder specialized in creating optimized day-by-day schedules.

You will receive:
1. Travel intent (dates, preferences, party size, food preferences)
2. List of POI candidates

Your task is to:
1. Distribute POIs across days (typically 3-4 POIs per day based on pace)
2. Cluster by geographic proximity to minimize travel
3. Create time blocks (09:00-18:30 typical day)
4. Insert lunch breaks (12:30-13:30) as separate blocks
5. Respect POI duration_min for visit length (these are already calculated based on POI type)
6. Match pace preference:
   - relaxed: 2-3 POIs per day, longer visits
   - moderate: 3-4 POIs per day
   - fast: 4-5 POIs per day, efficient scheduling
7. For lunch breaks:
   - If user has food_preferences (e.g., "pizza"), use nearby restaurants matching that cuisine
   - Otherwise, create generic "Lunch Break" with nearby coordinates
   - Set lunch break coordinates near the previous POI or between morning/afternoon activities

Output ONLY valid JSON matching this exact schema:
{
  "days": [
    {
      "date": "YYYY-MM-DD",
      "blocks": [
        {
          "start_time": "HH:MM",
          "end_time": "HH:MM",
          "poi": {
            "name": "string",
            "lat": number,
            "lon": number,
            "tags": ["string"],
            "duration_min": number,
            "booking_required": boolean,
            "booking_url": "string or null",
            "notes": "string or null",
            "open_hours": "string or null"
          },
          "travel_from_previous": number
        }
      ]
    }
  ]
}

Rules:
- No overlapping time blocks
- Start first activity around 09:00-09:30
- End last activity by 18:30
- Insert lunch break (12:30-13:30) with poi.name = "Lunch Break"
- Cluster POIs by neighborhood per day (group nearby attractions)
- Leave buffer time for travel between POIs
- Respect POI duration_min
- For lunch breaks, set duration_min to 60 and travel_from_previous to 0
 - Avoid repeating the same POI name across the entire trip unless the user explicitly asks to repeat
 - When a POI near a lunch break changes, refresh the lunch note (e.g., "Lunch near <neighbor>")

Example output structure:
{
  "days": [
    {
      "date": "2025-12-20",
      "blocks": [
        {
          "start_time": "09:00",
          "end_time": "12:00",
          "poi": {
            "name": "Statue of Liberty",
            "lat": 40.6892,
            "lon": -74.0445,
            "tags": ["landmark", "view"],
            "duration_min": 180,
            "booking_required": true,
            "booking_url": "https://...",
            "notes": "Ferry queues; go early",
            "open_hours": "09:00-17:00"
          },
          "travel_from_previous": 0
        },
        {
          "start_time": "12:30",
          "end_time": "13:30",
          "poi": {
            "name": "Lunch Break",
            "lat": 40.7128,
            "lon": -74.0060,
            "tags": ["food"],
            "duration_min": 60,
            "booking_required": false,
            "booking_url": null,
            "notes": "Lunch in Financial District",
            "open_hours": null
          },
          "travel_from_previous": 0
        },
        {
          "start_time": "14:00",
          "end_time": "16:30",
          "poi": {
            "name": "9/11 Memorial",
            "lat": 40.7115,
            "lon": -74.0134,
            "tags": ["memorial", "history"],
            "duration_min": 150,
            "booking_required": false,
            "booking_url": null,
            "notes": "Free admission",
            "open_hours": "09:00-20:00"
          },
          "travel_from_previous": 15
        }
      ]
    }
  ]
}

IMPORTANT: Return ONLY the JSON object, no additional text or explanation.
"""


def validate_schedule(days: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """
    Validate the generated schedule for common issues.
    
    Args:
        days: List of day dictionaries with blocks
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    for day_idx, day in enumerate(days):
        date = day.get("date", "unknown")
        blocks = day.get("blocks", [])
        
        if not blocks:
            errors.append(f"Day {day_idx + 1} ({date}) has no blocks")
            continue
        
        # Check for time overlaps
        for i in range(len(blocks) - 1):
            current_block = blocks[i]
            next_block = blocks[i + 1]
            
            try:
                current_end = datetime.strptime(current_block.get("end_time", ""), "%H:%M")
                next_start = datetime.strptime(next_block.get("start_time", ""), "%H:%M")
                
                if current_end > next_start:
                    errors.append(
                        f"Day {day_idx + 1}: Overlapping blocks - "
                        f"{current_block.get('poi', {}).get('name', 'Unknown')} ends at {current_block.get('end_time')} "
                        f"but {next_block.get('poi', {}).get('name', 'Unknown')} starts at {next_block.get('start_time')}"
                    )
            except (ValueError, AttributeError) as e:
                errors.append(f"Day {day_idx + 1}: Invalid time format - {e}")
        
        # Check for reasonable day length
        if blocks:
            try:
                first_start = datetime.strptime(blocks[0].get("start_time", ""), "%H:%M")
                last_end = datetime.strptime(blocks[-1].get("end_time", ""), "%H:%M")
                
                if first_start.hour < 6:
                    errors.append(f"Day {day_idx + 1}: Starts too early ({blocks[0].get('start_time')})")
                
                if last_end.hour > 22:
                    errors.append(f"Day {day_idx + 1}: Ends too late ({blocks[-1].get('end_time')})")
            except (ValueError, AttributeError):
                pass
        
        # Validate POI data
        for block_idx, block in enumerate(blocks):
            poi = block.get("poi", {})
            
            if not poi.get("name"):
                errors.append(f"Day {day_idx + 1}, Block {block_idx + 1}: Missing POI name")
            
            # Check coordinates (except for lunch breaks)
            if poi.get("name") != "Lunch Break":
                if poi.get("lat") is None or poi.get("lon") is None:
                    errors.append(
                        f"Day {day_idx + 1}, Block {block_idx + 1}: "
                        f"POI '{poi.get('name', 'Unknown')}' missing coordinates"
                    )
    
    is_valid = len(errors) == 0
    return is_valid, errors


def calculate_travel_times(days: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Calculate and update travel times between consecutive POIs.
    
    Args:
        days: List of day dictionaries with blocks
        
    Returns:
        Updated days list with travel_from_previous populated
    """
    for day in days:
        blocks = day.get("blocks", [])
        
        for i, block in enumerate(blocks):
            if i == 0:
                # First block of the day has no previous travel
                block["travel_from_previous"] = 0
            else:
                prev_block = blocks[i - 1]
                prev_poi = prev_block.get("poi", {})
                current_poi = block.get("poi", {})
                
                # Get coordinates
                prev_lat = prev_poi.get("lat")
                prev_lon = prev_poi.get("lon")
                curr_lat = current_poi.get("lat")
                curr_lon = current_poi.get("lon")
                
                # Special handling for lunch breaks
                if current_poi.get("name") == "Lunch Break":
                    # If lunch break has same coordinates as previous POI, no travel
                    if prev_lat == curr_lat and prev_lon == curr_lon:
                        block["travel_from_previous"] = 0
                    # Otherwise calculate travel time
                    elif all(coord is not None for coord in [prev_lat, prev_lon, curr_lat, curr_lon]):
                        try:
                            _, travel_time_min = calculate_distance(
                                prev_lat, prev_lon, curr_lat, curr_lon
                            )
                            block["travel_from_previous"] = travel_time_min
                        except Exception as e:
                            logger.warning(f"Failed to calculate travel time to lunch: {e}")
                            block["travel_from_previous"] = 10
                    else:
                        block["travel_from_previous"] = 0
                    continue
                
                # Calculate travel time for regular POIs
                if all(coord is not None for coord in [prev_lat, prev_lon, curr_lat, curr_lon]):
                    try:
                        _, travel_time_min = calculate_distance(
                            prev_lat, prev_lon, curr_lat, curr_lon
                        )
                        block["travel_from_previous"] = travel_time_min
                        logger.debug(
                            f"Travel time from {prev_poi.get('name')} to {current_poi.get('name')}: "
                            f"{travel_time_min} min"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to calculate travel time: {e}")
                        block["travel_from_previous"] = 15  # Default fallback
                else:
                    logger.warning(
                        f"Missing coordinates for travel calculation between "
                        f"{prev_poi.get('name')} and {current_poi.get('name')}"
                    )
                    block["travel_from_previous"] = 15  # Default fallback
    
    return days


def packager_node(state: TripState) -> TripState:
    """
    Packager agent: Build optimized itinerary with time blocks and artifacts.
    
    This node takes the POI candidates and intent, creates a day-by-day schedule,
    calculates travel times, and generates booking links, maps, and calendar exports.
    
    Args:
        state: Current TripState with intent and poi_candidates populated
        
    Returns:
        Updated TripState with days, links, map_geojson, and calendar_export populated
    """
    logger.info("Packager agent starting")
    
    try:
        intent = state.get("intent")
        poi_candidates = state.get("poi_candidates", [])
        
        if not intent:
            error_msg = "No intent found in state"
            logger.error(error_msg)
            state["errors"].append(f"Packager error: {error_msg}")
            state["status"] = "error"
            state["current_agent"] = "packager"
            return state
        
        if not poi_candidates:
            error_msg = "No POI candidates found in state"
            logger.error(error_msg)
            state["errors"].append(f"Packager error: {error_msg}")
            state["status"] = "error"
            state["current_agent"] = "packager"
            return state
        
        # Prepare prompt for LLM
        messages = [
            SystemMessage(content=PACKAGER_SYSTEM_PROMPT),
            HumanMessage(content=f"""
Intent: {json.dumps(intent, indent=2)}

POI Candidates ({len(poi_candidates)} total):
{json.dumps(poi_candidates, indent=2)}

Create an optimized {intent['nights']}-day itinerary with {intent['prefs']['pace']} pace.
Cluster POIs by geographic proximity for each day.
Include lunch breaks around 12:30-13:30.
""")
        ]
        
        # Invoke LLM
        logger.info(f"Invoking LLM to create {intent['nights']}-day itinerary")
        response = llm_provider.invoke_with_fallback(messages)
        
        # Parse JSON response
        response_content = response.content.strip()
        logger.debug(f"LLM response length: {len(response_content)} chars")
        
        # Handle potential markdown code blocks
        if response_content.startswith("```"):
            lines = response_content.split("\n")
            json_lines = []
            in_code_block = False
            for line in lines:
                if line.startswith("```"):
                    in_code_block = not in_code_block
                    continue
                if in_code_block or (not line.startswith("```")):
                    json_lines.append(line)
            response_content = "\n".join(json_lines).strip()
        
        schedule_data = json.loads(response_content)
        days = schedule_data.get("days", [])
        
        if not days:
            error_msg = "LLM returned empty schedule"
            logger.error(error_msg)
            state["errors"].append(f"Packager error: {error_msg}")
            state["status"] = "error"
            state["current_agent"] = "packager"
            return state
        
        logger.info(f"LLM generated {len(days)}-day schedule")

        # Post-process: de-duplicate POIs across the whole trip and refresh lunch notes
        def _dedupe_trip_and_refresh_lunch(days_in: List[Dict[str, Any]], candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            if not days_in:
                return days_in
            used: set = set()
            cand_list = candidates or []

            # First collect names in order and apply replacements when a name repeats (excluding Lunch Break)
            for day in days_in:
                blocks = day.get("blocks", []) or []
                for blk in blocks:
                    poi = blk.get("poi", {}) or {}
                    name = (poi.get("name") or "").strip()
                    if not name or name.lower() == "lunch break":
                        continue
                    if name in used:
                        # Try find a replacement with overlapping tags or similar hint
                        tags = {str(t).lower() for t in (poi.get("tags") or [])}
                        desired = set(tags)
                        # Heuristic: add keyword from name if present
                        lname = name.lower()
                        for kw in ["beach", "fort", "museum", "garden", "park", "market", "view"]:
                            if kw in lname:
                                desired.add(kw)
                        replacement = None
                        for cand in cand_list:
                            cname = (cand.get("name") or "").strip()
                            if not cname or cname in used:
                                continue
                            ctags = {str(t).lower() for t in (cand.get("tags") or [])}
                            if desired and (ctags & desired):
                                replacement = cand
                                break
                        if not replacement:
                            for cand in cand_list:
                                cname = (cand.get("name") or "").strip()
                                if cname and cname not in used:
                                    replacement = cand
                                    break
                        if replacement:
                            blk["poi"] = {
                                "name": replacement.get("name"),
                                "lat": replacement.get("lat"),
                                "lon": replacement.get("lon"),
                                "tags": replacement.get("tags", []),
                                "duration_min": replacement.get("duration_min", poi.get("duration_min", 60)),
                                "booking_required": replacement.get("booking_required", False),
                                "booking_url": replacement.get("booking_url"),
                                "notes": replacement.get("notes") or poi.get("notes"),
                                "open_hours": replacement.get("open_hours"),
                            }
                            used.add(replacement.get("name"))
                        else:
                            # If no replacement, keep but do not add duplicate again to used (already present)
                            pass
                    else:
                        used.add(name)

            # Refresh lunch notes referencing nearest neighbor name in sequence
            for day in days_in:
                blocks = day.get("blocks", []) or []
                for i, blk in enumerate(blocks):
                    poi = blk.get("poi", {}) or {}
                    if (poi.get("name") or "").strip().lower() == "lunch break":
                        neighbor = None
                        if i > 0:
                            neighbor = (blocks[i-1].get("poi", {}).get("name") or "").strip()
                        if not neighbor and i + 1 < len(blocks):
                            neighbor = (blocks[i+1].get("poi", {}).get("name") or "").strip()
                        poi["notes"] = f"Lunch near {neighbor}." if neighbor else "Lunch nearby."
                        blk["poi"] = poi

            return days_in

        try:
            days = _dedupe_trip_and_refresh_lunch(days, poi_candidates)
        except Exception as e:
            logger.warning(f"Trip-level dedupe/lunch refresh failed: {e}")
        
        # Calculate travel times between POIs
        logger.info("Calculating travel times between POIs")
        days = calculate_travel_times(days)
        
        # Validate schedule
        is_valid, validation_errors = validate_schedule(days)
        if not is_valid:
            logger.warning(f"Schedule validation found {len(validation_errors)} issues:")
            for error in validation_errors:
                logger.warning(f"  - {error}")
            # Continue anyway but log warnings
        
        # Generate booking links
        logger.info("Generating booking links")
        links = {}
        
        origin = intent.get("origin")
        city = intent.get("city")
        start_date = intent.get("start_date")
        nights = intent.get("nights")
        party = intent.get("party")
        
        if origin and city and start_date:
            try:
                # Calculate return date
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                return_dt = start_dt + timedelta(days=nights)
                return_date = return_dt.strftime("%Y-%m-%d")
                
                links["flights"] = build_flight_link(origin, city, start_date, return_date)
            except Exception as e:
                logger.warning(f"Failed to generate flight link: {e}")
                links["flights"] = ""
        else:
            links["flights"] = ""
        
        if city and start_date and nights and party:
            try:
                links["hotels"] = build_hotel_link(city, start_date, nights, party)
            except Exception as e:
                logger.warning(f"Failed to generate hotel link: {e}")
                links["hotels"] = ""
        else:
            links["hotels"] = ""
        
        # Generate map GeoJSON
        logger.info("Generating map GeoJSON")
        try:
            map_geojson = make_geojson(days)
        except Exception as e:
            logger.error(f"Failed to generate GeoJSON: {e}")
            map_geojson = {"type": "FeatureCollection", "features": []}
        
        # Generate calendar export
        logger.info("Generating calendar export")
        try:
            calendar_export = export_calendar(days, intent)
        except Exception as e:
            logger.error(f"Failed to generate calendar export: {e}")
            calendar_export = {"format": "ical", "events_count": 0, "ical_data": ""}
        
        # Update state
        state["days"] = days
        state["links"] = links
        state["map_geojson"] = map_geojson
        state["calendar_export"] = calendar_export
        state["status"] = "complete"
        state["current_agent"] = "packager"
        
        logger.info(
            f"Packager completed: {len(days)} days, "
            f"{sum(len(d.get('blocks', [])) for d in days)} blocks, "
            f"{len(map_geojson.get('features', []))} map features"
        )
        
        return state
        
    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse LLM response as JSON: {str(e)}"
        logger.error(error_msg)
        logger.error(f"Response content: {response.content if 'response' in locals() else 'N/A'}")
        state["errors"].append(f"Packager JSON error: {error_msg}")
        state["status"] = "error"
        state["current_agent"] = "packager"
        return state
        
    except Exception as e:
        error_msg = f"Packager agent failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        state["errors"].append(error_msg)
        state["status"] = "error"
        state["current_agent"] = "packager"
        return state


EDIT_PACKAGER_SYSTEM_PROMPT = """You are a travel itinerary editor specialized in making targeted updates to existing schedules.

You will receive:
1. Current trip schedule (days with time blocks)
2. An edit instruction specifying what to change
3. Replacement POIs (if applicable)

Your task is to:
1. Parse the edit instruction to identify which day(s) or block(s) to modify
2. Apply the requested changes (move, replace, remove, add POIs)
3. Recalculate time blocks to avoid overlaps
4. Maintain geographic clustering where possible
5. Return the complete updated schedule

Output ONLY valid JSON matching this exact schema:
{
  "modified_days": [number],
  "days": [
    {
      "date": "YYYY-MM-DD",
      "blocks": [
        {
          "start_time": "HH:MM",
          "end_time": "HH:MM",
          "poi": {POI object},
          "travel_from_previous": number
        }
      ]
    }
  ]
}

The "modified_days" array should contain the indices (0-based) of days that were changed.
The "days" array should contain the COMPLETE updated schedule for ALL days.

Edit types to handle:
- Move POI to different day: "Move X to day 3"
- Replace POI: "Replace X with Y"
- Remove POI: "Remove X from the schedule"
- Add POI: "Add X to day 2"
- Adjust timing: "Start earlier on day 1"
- Swap POIs: "Swap the order of X and Y"

 Rules:
- Maintain no overlapping time blocks
- Recalculate travel times between POIs
- Keep lunch breaks around 12:30-13:30
- Respect POI duration_min
- Maintain geographic clustering where possible
 - Avoid duplicate POI names across the entire trip unless the user explicitly requests a repeat (choose a similar alternative if needed)
- When a POI near a lunch break changes, refresh the lunch note (e.g., "Lunch near <neighbor>")
- Update only affected days, but return complete schedule

Example:

Input:
Current Schedule: Day 1 has [POI A (09:00-11:00), Lunch (12:30-13:30), POI B (14:00-16:00)]
Edit: "Replace POI B with POI C"
Replacement POIs: [{"name": "POI C", "duration_min": 120, ...}]

Output: {
  "modified_days": [0],
  "days": [
    {
      "date": "2025-12-20",
      "blocks": [
        {"start_time": "09:00", "end_time": "11:00", "poi": {POI A}, ...},
        {"start_time": "12:30", "end_time": "13:30", "poi": {Lunch}, ...},
        {"start_time": "14:00", "end_time": "16:00", "poi": {POI C}, ...}
      ]
    },
    ... (other days unchanged)
  ]
}

IMPORTANT: Return ONLY the JSON object, no additional text or explanation.
"""


def edit_packager_node(state: TripState) -> TripState:
    """
    Edit packager agent: Update specific days/blocks in the itinerary.
    
    This node applies targeted edits to the existing schedule, modifying only
    the affected portions while maintaining schedule validity and recalculating
    travel times.
    
    Args:
        state: Current TripState with days, edit_instruction, and replacement_pois
        
    Returns:
        Updated TripState with modified days and updated artifacts
    """
    logger.info("Edit packager agent starting")
    
    try:
        intent = state.get("intent")
        current_days = state.get("days", [])
        edit_instruction = state.get("edit_instruction", state.get("user_input", ""))
        replacement_pois = state.get("replacement_pois", [])
        needs_new_pois = state.get("needs_new_pois", False)
        
        if not intent:
            error_msg = "Cannot edit without existing intent"
            logger.error(error_msg)
            state["errors"].append(error_msg)
            state["status"] = "error"
            state["current_agent"] = "edit_packager"
            return state
        
        if not current_days:
            error_msg = "Cannot edit without existing schedule"
            logger.error(error_msg)
            state["errors"].append(error_msg)
            state["status"] = "error"
            state["current_agent"] = "edit_packager"
            return state
        
        # Prepare messages for LLM
        messages = [
            SystemMessage(content=EDIT_PACKAGER_SYSTEM_PROMPT),
            HumanMessage(content=f"""
Current Schedule:
{json.dumps(current_days, indent=2)}

Edit Instruction:
{edit_instruction}

Replacement POIs Available:
{json.dumps(replacement_pois, indent=2) if replacement_pois else "None"}

Apply the edit to the schedule and return the complete updated itinerary.
Mark which days were modified in the modified_days array.
""")
        ]
        
        # Invoke LLM with fallback support
        logger.info("Invoking LLM to apply schedule edits")
        response = llm_provider.invoke_with_fallback(messages)
        
        # Parse JSON response
        response_content = response.content.strip()
        logger.debug(f"LLM response length: {len(response_content)} chars")
        
        # Handle potential markdown code blocks
        if response_content.startswith("```"):
            lines = response_content.split("\n")
            json_lines = []
            in_code_block = False
            for line in lines:
                if line.startswith("```"):
                    in_code_block = not in_code_block
                    continue
                if in_code_block or (not line.startswith("```")):
                    json_lines.append(line)
            response_content = "\n".join(json_lines).strip()
        
        edit_schedule_data = json.loads(response_content)
        
        # Extract results
        modified_days_indices = edit_schedule_data.get("modified_days", [])
        updated_days = edit_schedule_data.get("days", current_days)
        
        if not updated_days:
            error_msg = "LLM returned empty schedule"
            logger.error(error_msg)
            state["errors"].append(f"Edit packager error: {error_msg}")
            state["status"] = "error"
            state["current_agent"] = "edit_packager"
            return state
        
        logger.info(f"LLM updated schedule: {len(modified_days_indices)} days modified")

        # Post-process schedule: dedupe POIs per day and refresh lunch notes
        def _fix_duplicates_and_lunch(days: List[Dict[str, Any]], candidates: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[int]]:
            modified_idx: List[int] = []
            cand_list = candidates or []
            global_used: set = set()
            for d_idx, day in enumerate(days or []):
                blocks = day.get("blocks", []) or []
                for b in blocks:
                    poi = b.get("poi", {}) or {}
                    name = (poi.get("name") or "").strip()
                    if not name or name.lower() == "lunch break":
                        continue
                    if name in global_used:
                        # Replace duplicate with a similar unused candidate
                        tags = {str(t).lower() for t in (poi.get("tags") or [])}
                        desired = set(tags)
                        lname = name.lower()
                        for kw in ["beach", "fort", "museum", "garden", "park", "market", "view"]:
                            if kw in lname:
                                desired.add(kw)
                        replacement = None
                        for cand in cand_list:
                            cname = (cand.get("name") or "").strip()
                            if not cname or cname in global_used:
                                continue
                            ctags = {str(t).lower() for t in (cand.get("tags") or [])}
                            if desired and (ctags & desired):
                                replacement = cand
                                break
                        if not replacement:
                            for cand in cand_list:
                                cname = (cand.get("name") or "").strip()
                                if cname and cname not in global_used:
                                    replacement = cand
                                    break
                        if replacement:
                            b["poi"] = {
                                "name": replacement.get("name"),
                                "lat": replacement.get("lat"),
                                "lon": replacement.get("lon"),
                                "tags": replacement.get("tags", []),
                                "duration_min": replacement.get("duration_min", poi.get("duration_min", 60)),
                                "booking_required": replacement.get("booking_required", False),
                                "booking_url": replacement.get("booking_url"),
                                "notes": replacement.get("notes") or poi.get("notes"),
                                "open_hours": replacement.get("open_hours"),
                            }
                            global_used.add(replacement.get("name"))
                            if d_idx not in modified_idx:
                                modified_idx.append(d_idx)
                        # If no replacement found, keep as duplicate (last resort)
                    else:
                        global_used.add(name)

                # Refresh lunch notes
                for i, blk in enumerate(blocks):
                    p = blk.get("poi", {}) or {}
                    if (p.get("name") or "").strip().lower() == "lunch break":
                        neighbor = None
                        if i > 0:
                            neighbor = (blocks[i-1].get("poi", {}).get("name") or "").strip()
                        if not neighbor and i+1 < len(blocks):
                            neighbor = (blocks[i+1].get("poi", {}).get("name") or "").strip()
                        new_note = f"Lunch near {neighbor}." if neighbor else "Lunch nearby."
                        if p.get("notes") != new_note:
                            p["notes"] = new_note
                            blk["poi"] = p
                            if d_idx not in modified_idx:
                                modified_idx.append(d_idx)
            return days, sorted(list(set(modified_idx)))

        try:
            updated_days, post_mod = _fix_duplicates_and_lunch(updated_days, state.get("poi_candidates", []))
            if post_mod:
                logger.info(f"Post-processed schedule: fixed duplicates/lunch notes on days {post_mod}")
                modified_days_indices = sorted(list(set(modified_days_indices + post_mod)))
        except Exception as e:
            logger.warning(f"Post-process adjustments failed: {e}")

        # Recalculate travel times for modified days
        logger.info("Recalculating travel times for modified days")
        updated_days = calculate_travel_times(updated_days)
        
        # Validate updated schedule
        is_valid, validation_errors = validate_schedule(updated_days)
        if not is_valid:
            logger.warning(f"Updated schedule validation found {len(validation_errors)} issues:")
            for error in validation_errors:
                logger.warning(f"  - {error}")
            # Continue anyway but log warnings
        
        # Regenerate artifacts for modified portions
        logger.info("Regenerating artifacts (map, calendar)")
        
        # Update map GeoJSON
        try:
            map_geojson = make_geojson(updated_days)
        except Exception as e:
            logger.error(f"Failed to regenerate GeoJSON: {e}")
            map_geojson = state.get("map_geojson", {"type": "FeatureCollection", "features": []})
        
        # Update calendar export
        try:
            calendar_export = export_calendar(updated_days, intent)
        except Exception as e:
            logger.error(f"Failed to regenerate calendar export: {e}")
            calendar_export = state.get("calendar_export", {"format": "ical", "events_count": 0})
        
        # Update state
        state["days"] = updated_days
        state["modified_days"] = modified_days_indices
        state["map_geojson"] = map_geojson
        state["calendar_export"] = calendar_export
        state["status"] = "edit_complete"
        state["current_agent"] = "edit_packager"
        
        logger.info(
            f"Edit packager completed: {len(modified_days_indices)} days modified, "
            f"{len(updated_days)} total days in schedule"
        )
        
        return state
        
    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse LLM response as JSON: {str(e)}"
        logger.error(error_msg)
        logger.error(f"Response content: {response.content if 'response' in locals() else 'N/A'}")
        state["errors"].append(f"Edit packager JSON error: {error_msg}")
        state["status"] = "error"
        state["current_agent"] = "edit_packager"
        return state
        
    except Exception as e:
        error_msg = f"Edit packager agent failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        state["errors"].append(error_msg)
        state["status"] = "error"
        state["current_agent"] = "edit_packager"
        return state
