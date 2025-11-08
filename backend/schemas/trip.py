"""
Pydantic schemas for trip data structures.
Matches the structure defined in docs/sample_trip_response.json
"""
from typing import List, Dict, Optional, Literal
from pydantic import BaseModel, Field


# ============================================================================
# INTERNAL MODELS (Used by agents/tools internally)
# ============================================================================

class POI(BaseModel):
    """Internal POI model with all fields from OpenTripMap/GraphDB"""
    id: str
    name: str
    lat: float
    lon: float
    city: str
    neighborhood: Optional[str] = None
    tags: List[str] = []
    duration_min: Optional[int] = None
    popularity: Optional[float] = None
    booking_required: bool = False
    booking_url: Optional[str] = None
    hours: Optional[Dict] = None  # {"mon":[["09:00","17:00"]], ..., "tz":"America/New_York"}
    notes: List[str] = []
    source: str
    source_id: str


# ============================================================================
# API RESPONSE MODELS (Sent to frontend)
# ============================================================================

class Activity(BaseModel):
    """Single activity in a day's itinerary"""
    time: str = Field(..., description="Start time in HH:MM format", example="09:00")
    name: str = Field(..., description="Activity name", example="Statue of Liberty")
    type: Literal["attraction", "food"] = Field(..., description="Type of activity")
    lat: float = Field(..., description="Latitude coordinate")
    lon: float = Field(..., description="Longitude coordinate")
    duration_min: int = Field(..., description="Duration in minutes", example=180)
    booking_required: Optional[bool] = Field(default=False, description="Whether booking is required")
    booking_url: Optional[str] = Field(default=None, description="URL for booking")
    notes: Optional[str] = Field(default=None, description="Additional notes or tips")


class Day(BaseModel):
    """A single day in the trip itinerary"""
    date: str = Field(..., description="Date in YYYY-MM-DD format", example="2025-12-20")
    activities: List[Activity] = Field(..., description="List of activities for this day")


class BookingLinks(BaseModel):
    """External booking links for flights and hotels"""
    flights: str = Field(..., description="Google Flights deep link")
    hotels: str = Field(..., description="Booking.com deep link")


class TripResponse(BaseModel):
    """Complete trip response sent to frontend"""
    trip_id: str = Field(..., description="Unique trip identifier", example="trip_12345")
    status: Literal["processing", "completed", "failed"] = Field(
        ..., 
        description="Current status of trip generation"
    )
    city: str = Field(..., description="Destination city", example="New York City, NY")
    origin: str = Field(..., description="Origin city", example="Buffalo, NY")
    start_date: str = Field(..., description="Trip start date in YYYY-MM-DD format")
    end_date: str = Field(..., description="Trip end date in YYYY-MM-DD format")
    days: List[Day] = Field(..., description="Day-by-day itinerary")
    booking_links: BookingLinks = Field(..., description="Flight and hotel booking links")

    class Config:
        json_schema_extra = {
            "example": {
                "trip_id": "trip_12345",
                "status": "completed",
                "city": "New York City, NY",
                "origin": "Buffalo, NY",
                "start_date": "2025-12-20",
                "end_date": "2025-12-22",
                "days": [
                    {
                        "date": "2025-12-20",
                        "activities": [
                            {
                                "time": "09:00",
                                "name": "Statue of Liberty",
                                "type": "attraction",
                                "lat": 40.6892,
                                "lon": -74.0445,
                                "duration_min": 180,
                                "booking_required": True,
                                "booking_url": "https://www.statuecitycruises.com/"
                            }
                        ]
                    }
                ],
                "booking_links": {
                    "flights": "https://www.google.com/travel/flights?...",
                    "hotels": "https://www.booking.com/searchresults.html?..."
                }
            }
        }
