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
1. Travel intent (dates, preferences, party size)
2. List of POI candidates

Your task is to:
1. Distribute POIs across days (typically 3-4 POIs per day based on pace)
2. Cluster by geographic proximity to minimize travel
3. Create time blocks (09:00-18:30 typical day)
4. Insert lunch breaks (12:30-13:30) as separate blocks
5. Respect POI duration_min for visit length
6. Match pace preference:
   - relaxed: 2-3 POIs per day, longer visits
   - moderate: 3-4 POIs per day
   - fast: 4-5 POIs per day, efficient scheduling

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
                
                # Skip travel calculation for lunch breaks
                if current_poi.get("name") == "Lunch Break":
                    block["travel_from_previous"] = 0
                    continue
                
                # Get coordinates
                prev_lat = prev_poi.get("lat")
                prev_lon = prev_poi.get("lon")
                curr_lat = current_poi.get("lat")
                curr_lon = current_poi.get("lon")
                
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
