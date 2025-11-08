"""
API routes for trip creation and management
"""
import uuid
from typing import Dict
from fastapi import APIRouter, HTTPException
from backend.schemas import CreateTripRequest, EditTripRequest, TripResponse

router = APIRouter(prefix="/api", tags=["trips"])

# Temporary in-memory storage (DevOps will replace with actual database)
trips_store: Dict[str, dict] = {}


def generate_trip_id() -> str:
    """Generate unique trip ID"""
    return f"trip_{uuid.uuid4().hex[:8]}"


@router.post("/trip")
async def create_trip(request: CreateTripRequest):
    """
    Create a new trip from natural language prompt
    
    Returns immediately with trip_id and 'processing' status.
    The agent workflow runs in background (will implement async later).
    """
    trip_id = generate_trip_id()
    
    # Store initial state
    trips_store[trip_id] = {
        "trip_id": trip_id,
        "status": "processing",
        "prompt": request.prompt
    }
    
    # TODO: Trigger LangGraph workflow asynchronously
    # For now, just return processing status
    
    return {
        "trip_id": trip_id,
        "status": "processing"
    }


@router.get("/trip/{trip_id}", response_model=TripResponse)
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
    
    # Return complete trip data
    return trip_data


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
    
    # TODO: Run LangGraph workflow with edit instruction
    # For now, just return existing data
    
    return trip_data

