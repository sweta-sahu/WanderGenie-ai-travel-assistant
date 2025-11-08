"""
Pydantic schemas for WanderGenie API
"""
from .trip import POI, Activity, Day, BookingLinks, TripResponse
from .requests import CreateTripRequest, EditTripRequest

__all__ = [
    # Internal models
    "POI",
    # API response models
    "Activity",
    "Day",
    "BookingLinks",
    "TripResponse",
    # API request models
    "CreateTripRequest",
    "EditTripRequest",
]
