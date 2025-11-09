"""
State schema definitions for the LangGraph travel planning workflow.

This module defines all TypedDict classes that make up the TripState,
which flows through the Planner, Researcher, and Packager agents.
"""

from typing import TypedDict, List, Dict, Optional, Literal


class PartyComposition(TypedDict):
    """Party composition for the trip."""
    adults: int
    children: int
    teens: int


class TravelPreferences(TypedDict):
    """User travel preferences and constraints."""
    pace: Literal["relaxed", "moderate", "fast"]
    interests: List[str]
    constraints: List[str]
    food_preferences: List[str]  # Specific food preferences (e.g., ["pizza", "sushi"])


class Intent(TypedDict):
    """Structured travel intent extracted from user input."""
    city: str
    origin: Optional[str]
    start_date: str
    nights: int
    party: PartyComposition
    prefs: TravelPreferences


class POICandidate(TypedDict):
    """Point of Interest candidate with metadata."""
    name: str
    lat: float
    lon: float
    tags: List[str]
    duration_min: int
    booking_required: bool
    booking_url: Optional[str]
    notes: Optional[str]
    open_hours: Optional[str]


class TimeBlock(TypedDict):
    """Time block within a day's schedule."""
    start_time: str
    end_time: str
    poi: POICandidate
    travel_from_previous: int  # minutes


class Day(TypedDict):
    """Single day in the itinerary."""
    date: str
    blocks: List[TimeBlock]


class TripState(TypedDict):
    """
    Main state object that flows through the LangGraph workflow.
    
    This state is progressively enriched by each agent:
    - Planner: Populates intent
    - Researcher: Populates poi_candidates
    - Packager: Populates days, links, map_geojson, calendar_export
    
    For edit workflows:
    - Edit Planner: Updates intent based on edit_instruction
    - Edit Researcher: Finds replacement_pois if needed
    - Edit Packager: Updates specific days/blocks
    """
    # Input
    user_input: str
    trip_id: Optional[str]
    
    # Planner output
    intent: Optional[Intent]
    
    # Researcher output
    poi_candidates: List[POICandidate]
    
    # Packager output
    days: List[Day]
    links: Dict[str, str]
    map_geojson: Dict
    calendar_export: Dict
    
    # Edit workflow fields (all optional for backward compatibility)
    edit_instruction: Optional[str]
    edit_type: Optional[str]  # "intent_change", "preference_change", "no_change"
    needs_new_pois: Optional[bool]
    replacement_pois: List[POICandidate]  # Empty list by default
    modified_days: List[int]  # Empty list by default, indices of days that were modified
    
    # Metadata
    status: str
    current_agent: Optional[str]
    errors: List[str]
