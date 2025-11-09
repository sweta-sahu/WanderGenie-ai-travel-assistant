"""
API routes for trip creation and management
"""
import uuid
import asyncio
import logging
from typing import Dict, List, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from backend.schemas import CreateTripRequest, EditTripRequest, TripResponse
from backend.agents.graph import trip_graph, edit_graph
from backend.agents.state import TripState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["trips"])

# Temporary in-memory storage (DevOps will replace with actual database)
trips_store: Dict[str, dict] = {}


def generate_trip_id() -> str:
    """Generate unique trip ID"""
    return f"trip_{uuid.uuid4().hex[:8]}"


def _blocks_to_activities(days: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert internal day blocks to API activities schema.

    Internal structure uses days[].blocks with time ranges and nested POIs.
    API expects days[].activities with flattened fields.
    """
    converted_days: List[Dict[str, Any]] = []

    for day in days or []:
        date = day.get("date", "")
        blocks = day.get("blocks", []) or []

        activities: List[Dict[str, Any]] = []
        for block in blocks:
            poi = block.get("poi", {}) or {}
            if not poi:
                continue

            tags = poi.get("tags") or []
            name = (poi.get("name") or "").strip()
            # Determine activity type
            tag_set = {str(t).lower() for t in tags}
            act_type = "food" if ("food" in tag_set or name.lower() == "lunch break") else "attraction"

            # Duration: prefer explicit poi.duration_min, else derive from times
            duration_min = poi.get("duration_min")
            if not duration_min:
                try:
                    start = block.get("start_time")
                    end = block.get("end_time")
                    if start and end and len(start) == 5 and len(end) == 5:
                        sh, sm = map(int, start.split(":"))
                        eh, em = map(int, end.split(":"))
                        duration_min = max(0, (eh * 60 + em) - (sh * 60 + sm))
                except Exception:
                    duration_min = None

            # Normalize notes (string or list)
            notes = poi.get("notes")
            if isinstance(notes, list):
                notes = "; ".join([str(n) for n in notes if n]) if notes else None

            activities.append(
                {
                    "time": block.get("start_time", ""),
                    "name": name,
                    "type": act_type,
                    "lat": poi.get("lat"),
                    "lon": poi.get("lon"),
                    "duration_min": duration_min or 0,
                    "booking_required": poi.get("booking_required", False),
                    "booking_url": poi.get("booking_url"),
                    "notes": notes,
                }
            )

        converted_days.append({"date": date, "activities": activities})

    return converted_days


def _assemble_trip_response(trip_id: str, status: str, intent: Dict[str, Any], days: List[Dict[str, Any]], links: Dict[str, str]) -> Dict[str, Any]:
    """Build TripResponse dict from internal state parts, converting days format."""
    # Compute end_date if possible (start_date + nights), else fallback to start_date
    def _s(val: Any) -> str:
        return val if isinstance(val, str) else ""

    city = _s(intent.get("city"))
    origin = _s(intent.get("origin"))
    start_date = _s(intent.get("start_date"))
    end_date = start_date
    try:
        nights = int(intent.get("nights")) if intent.get("nights") is not None else None
        if start_date and nights is not None:
            from datetime import datetime, timedelta

            dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_date = (dt + timedelta(days=nights)).strftime("%Y-%m-%d")
    except Exception:
        # keep fallback end_date = start_date
        pass

    days_converted = _blocks_to_activities(days)

    flights = links.get("flights", "") if isinstance(links, dict) else ""
    hotels = links.get("hotels", "") if isinstance(links, dict) else ""

    return {
        "trip_id": trip_id,
        "status": status,
        "city": city,
        "origin": origin,
        "start_date": start_date,
        "end_date": end_date,
        "days": days_converted,
        "booking_links": {"flights": flights, "hotels": hotels},
    }


def run_trip_workflow(trip_id: str, user_input: str):
    """
    Run the LangGraph workflow to generate trip itinerary.
    
    This function is called in the background after the API returns.
    It invokes the agent workflow and stores the result.
    """
    try:
        logger.info(f"Starting trip workflow for {trip_id}")
        
        # Check if trip_graph was initialized
        if trip_graph is None:
            error_msg = "LangGraph workflow not initialized"
            logger.error(error_msg)
            trips_store[trip_id] = {
                "trip_id": trip_id,
                "status": "failed",
                "error": error_msg
            }
            return
        
        # Initialize state
        initial_state: TripState = {
            "user_input": user_input,
            "trip_id": trip_id,
            "intent": None,
            "poi_candidates": [],
            "days": [],
            "links": {},
            "map_geojson": {},
            "calendar_export": {},
            "edit_instruction": None,
            "edit_type": None,
            "needs_new_pois": None,
            "replacement_pois": [],
            "modified_days": [],
            "status": "processing",
            "current_agent": None,
            "errors": []
        }
        
        # Invoke the workflow with config for checkpointer
        logger.info(f"Invoking trip_graph for {trip_id}")
        config = {"configurable": {"thread_id": trip_id}}
        final_state = trip_graph.invoke(initial_state, config=config)
        
        # Convert state to API response format
        if final_state["status"] == "error":
            trips_store[trip_id] = {
                "trip_id": trip_id,
                "status": "failed",
                "errors": final_state["errors"]
            }
            logger.error(f"Trip workflow failed for {trip_id}: {final_state['errors']}")
            return
        
        # Extract data from state
        intent = final_state.get("intent", {})
        days_data = final_state.get("days", [])
        links = final_state.get("links", {})
        
        # Calculate end_date properly
        start_date = intent.get("start_date", "")
        nights = intent.get("nights", 0)
        end_date = start_date
        
        if start_date and nights:
            try:
                from datetime import datetime, timedelta
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                end_dt = start_dt + timedelta(days=nights)
                end_date = end_dt.strftime("%Y-%m-%d")
            except Exception as e:
                logger.warning(f"Failed to calculate end_date: {e}")
                end_date = start_date
        
        # Convert to API response format
        trip_response = {
            "trip_id": trip_id,
            "status": "completed",
            "city": intent.get("city", ""),
            "origin": intent.get("origin", ""),
            "start_date": start_date,
            "end_date": end_date,
            "days": days_data,
            "booking_links": links
        }
        
        # Persist public response and internal metadata for future edits
        trip_response["_internal"] = {
            "intent": intent,
            "poi_candidates": final_state.get("poi_candidates", []),
            # Save original blocks-based days for edit workflows
            "days_blocks": days_data,
            "links": links,
        }
        trips_store[trip_id] = trip_response
        logger.info(f"Trip workflow completed successfully for {trip_id}")
        
    except Exception as e:
        error_msg = f"Workflow execution failed: {str(e)}"
        logger.error(f"Error in trip workflow for {trip_id}: {error_msg}", exc_info=True)
        trips_store[trip_id] = {
            "trip_id": trip_id,
            "status": "failed",
            "error": error_msg
        }


@router.post("/trip")
async def create_trip(request: CreateTripRequest, background_tasks: BackgroundTasks):
    """
    Create a new trip from natural language prompt
    
    Returns immediately with trip_id and 'processing' status.
    The agent workflow runs in background.
    """
    trip_id = generate_trip_id()
    
    # Store initial state
    trips_store[trip_id] = {
        "trip_id": trip_id,
        "status": "processing",
        "prompt": request.prompt
    }
    
    # Trigger LangGraph workflow in background
    background_tasks.add_task(run_trip_workflow, trip_id, request.prompt)
    
    logger.info(f"Created trip {trip_id}, workflow queued")
    
    return {
        "trip_id": trip_id,
        "status": "processing"
    }


@router.get("/trip/{trip_id}")
async def get_trip(trip_id: str):
    """
    Get trip details by ID
    
    Returns complete trip itinerary if processing is done,
    or status='processing' if still working.
    """
    if trip_id not in trips_store:
        raise HTTPException(status_code=404, detail="Trip not found")
    
    trip_data = trips_store[trip_id]
    
    # If still processing, return minimal response
    if trip_data["status"] == "processing":
        return {
            "trip_id": trip_id,
            "status": "processing",
            "city": "",
            "origin": "",
            "start_date": "",
            "end_date": "",
            "days": [],
            "booking_links": {"flights": "", "hotels": ""}
        }
    
    # Return complete trip data (exclude internal metadata if present)
    if isinstance(trip_data, dict) and "_internal" in trip_data:
        public = {k: v for k, v in trip_data.items() if k != "_internal"}
        return public
    return trip_data


@router.post("/trip/sync")
async def create_trip_sync(request: CreateTripRequest):
    """
    Create trip synchronously (for testing/debugging).
    This blocks until the trip is fully generated.
    """
    trip_id = generate_trip_id()
    
    try:
        logger.info(f"Starting synchronous trip creation for {trip_id}")
        
        # Initialize state
        initial_state: TripState = {
            "user_input": request.prompt,
            "trip_id": trip_id,
            "intent": None,
            "poi_candidates": [],
            "days": [],
            "links": {},
            "map_geojson": {},
            "calendar_export": {},
            "edit_instruction": None,
            "edit_type": None,
            "needs_new_pois": None,
            "replacement_pois": [],
            "modified_days": [],
            "status": "processing",
            "current_agent": None,
            "errors": []
        }
        
        # Run workflow synchronously
        config = {"configurable": {"thread_id": trip_id}}
        final_state = trip_graph.invoke(initial_state, config=config)
        
        if final_state["status"] == "error" or final_state.get("errors"):
            return {
                "trip_id": trip_id,
                "status": "failed",
                "errors": final_state.get("errors", ["Unknown error"])
            }
        
        # Extract data and assemble API response
        intent = final_state.get("intent", {})
        days_data = final_state.get("days", [])
        links = final_state.get("links", {})
        
        # Calculate end_date properly
        start_date = intent.get("start_date", "")
        nights = intent.get("nights", 0)
        end_date = start_date
        
        if start_date and nights:
            try:
                from datetime import datetime, timedelta
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                end_dt = start_dt + timedelta(days=nights)
                end_date = end_dt.strftime("%Y-%m-%d")
            except Exception as e:
                logger.warning(f"Failed to calculate end_date: {e}")
                end_date = start_date
        
        return {
            "trip_id": trip_id,
            "status": "completed",
            "city": intent.get("city", ""),
            "origin": intent.get("origin", ""),
            "start_date": start_date,
            "end_date": end_date,
            "days": days_data,
            "booking_links": links
        }
        
    except Exception as e:
        logger.error(f"Sync trip creation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/trip/{trip_id}", response_model=TripResponse)
async def edit_trip(trip_id: str, request: EditTripRequest):
    """
    Edit existing trip with natural language instruction
    
    Example: "Swap Day 2 afternoon for MoMA"
    """
    if trip_id not in trips_store:
        raise HTTPException(status_code=404, detail="Trip not found")
    
    trip_data = trips_store[trip_id]
    
    if trip_data["status"] == "processing":
        raise HTTPException(
            status_code=409, 
            detail="Trip is still being generated. Please wait."
        )
    
    # Build initial state for edit workflow
    edit_instruction = request.instruction

    # Prefer internal saved state when available
    internal = trip_data.get("_internal", {}) if isinstance(trip_data, dict) else {}

    # Intent: use saved, else construct defaults from stored trip
    saved_intent = internal.get("intent") or {}
    if not saved_intent:
        # Derive nights from end_date or number of days
        try:
            start_date = trip_data.get("start_date", "")
            end_date = trip_data.get("end_date", "")
            nights = None
            if start_date and end_date:
                from datetime import datetime

                sd = datetime.strptime(start_date, "%Y-%m-%d")
                ed = datetime.strptime(end_date, "%Y-%m-%d")
                nights = max(0, (ed - sd).days)
            if nights is None:
                nights = len(trip_data.get("days", [])) or 3
        except Exception:
            nights = len(trip_data.get("days", [])) or 3

        saved_intent = {
            "city": trip_data.get("city", ""),
            "origin": trip_data.get("origin", None),
            "start_date": trip_data.get("start_date", ""),
            "nights": int(nights),
            "party": {"adults": 2, "children": 0, "teens": 0},
            "prefs": {"pace": "moderate", "interests": [], "constraints": []},
        }

    # Days in internal format (blocks)
    def _activities_to_blocks(days_api: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        blocks_days: List[Dict[str, Any]] = []
        for d in days_api or []:
            date = d.get("date", "")
            activities = d.get("activities", []) or []
            blocks: List[Dict[str, Any]] = []
            for a in activities:
                time = a.get("time") or ""
                duration = a.get("duration_min") or 0
                # Compute end_time from time + duration
                end_time = ""
                try:
                    if time and len(time) == 5:
                        h, m = map(int, time.split(":"))
                        total = h * 60 + m + int(duration)
                        eh, em = divmod(max(0, total), 60)
                        eh = eh % 24
                        end_time = f"{eh:02d}:{em:02d}"
                except Exception:
                    end_time = ""

                tags: List[str] = []
                if str(a.get("type", "")).lower() == "food":
                    tags = ["food"]

                poi = {
                    "name": a.get("name", ""),
                    "lat": a.get("lat"),
                    "lon": a.get("lon"),
                    "tags": tags,
                    "duration_min": duration,
                    "booking_required": a.get("booking_required", False),
                    "booking_url": a.get("booking_url"),
                    "notes": a.get("notes"),
                    "open_hours": None,
                }
                blocks.append(
                    {
                        "start_time": time,
                        "end_time": end_time,
                        "poi": poi,
                        "travel_from_previous": 0,
                    }
                )

            blocks_days.append({"date": date, "blocks": blocks})
        return blocks_days

    days_blocks = internal.get("days_blocks")
    if not days_blocks:
        # If API shape, convert activities -> blocks; else assume already blocks
        stored_days = trip_data.get("days", [])
        if stored_days and "activities" in (stored_days[0] or {}):
            days_blocks = _activities_to_blocks(stored_days)
        else:
            days_blocks = stored_days

    # POI candidates: prefer saved; else derive from current blocks
    poi_candidates = internal.get("poi_candidates") or []
    if not poi_candidates:
        poi_candidates = []
        for day in days_blocks or []:
            for block in (day.get("blocks") or []):
                poi = block.get("poi") or {}
                if poi:
                    poi_candidates.append(
                        {
                            "name": poi.get("name"),
                            "lat": poi.get("lat"),
                            "lon": poi.get("lon"),
                            "tags": poi.get("tags") or [],
                            "duration_min": poi.get("duration_min") or 0,
                            "booking_required": poi.get("booking_required", False),
                            "booking_url": poi.get("booking_url"),
                            "notes": poi.get("notes"),
                            "open_hours": poi.get("open_hours"),
                        }
                    )

    # Links
    links = trip_data.get("booking_links", {}) or internal.get("links", {}) or {}

    # Prepare initial edit state
    initial_state: Dict[str, Any] = {
        "user_input": edit_instruction,
        "trip_id": trip_id,
        "intent": saved_intent,
        "poi_candidates": poi_candidates,
        "days": days_blocks,
        "links": links,
        "map_geojson": {},
        "calendar_export": {},
        "edit_instruction": edit_instruction,
        "edit_type": None,
        "needs_new_pois": None,
        "replacement_pois": [],
        "modified_days": [],
        "status": "processing",
        "current_agent": None,
        "errors": [],
    }

    # Run edit graph
    if edit_graph is None:
        raise HTTPException(status_code=500, detail="Edit workflow not initialized")

    config = {"configurable": {"thread_id": trip_id}}
    final_state = edit_graph.invoke(initial_state, config=config)

    if final_state.get("status") == "error" or final_state.get("errors"):
        raise HTTPException(status_code=500, detail={"errors": final_state.get("errors", ["Edit failed"])})

    # Assemble API response and update store
    updated_intent = final_state.get("intent", saved_intent)
    updated_days_blocks = final_state.get("days", days_blocks)
    updated_links = final_state.get("links", links)

    response = _assemble_trip_response(
        trip_id=trip_id,
        status="completed",
        intent=updated_intent or {},
        days=updated_days_blocks or [],
        links=updated_links or {},
    )

    # Persist updated trip with internal metadata
    response["_internal"] = {
        "intent": updated_intent,
        "poi_candidates": final_state.get("poi_candidates", poi_candidates),
        "days_blocks": updated_days_blocks,
        "links": updated_links,
    }
    trips_store[trip_id] = response

    return {k: v for k, v in response.items() if k != "_internal"}

