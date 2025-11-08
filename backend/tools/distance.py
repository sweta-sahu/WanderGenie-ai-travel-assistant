"""
Distance calculation tool.

This module provides functions to calculate travel time and distance
between points of interest.
"""

import logging
import math
from typing import Tuple

logger = logging.getLogger(__name__)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on Earth.
    
    Args:
        lat1: Latitude of first point
        lon1: Longitude of first point
        lat2: Latitude of second point
        lon2: Longitude of second point
        
    Returns:
        Distance in kilometers
    """
    # Earth radius in kilometers
    R = 6371.0
    
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    distance = R * c
    return distance


def calculate_distance(
    from_lat: float,
    from_lon: float,
    to_lat: float,
    to_lon: float
) -> Tuple[float, int]:
    """
    Calculate distance and estimated travel time between two POIs.
    
    Uses haversine formula for distance and estimates travel time
    based on average urban travel speed.
    
    Args:
        from_lat: Starting point latitude
        from_lon: Starting point longitude
        to_lat: Destination latitude
        to_lon: Destination longitude
        
    Returns:
        Tuple of (distance_km, travel_time_minutes)
    """
    distance_km = haversine_distance(from_lat, from_lon, to_lat, to_lon)
    
    # Estimate travel time based on distance
    # Assume average urban travel speed of 20 km/h (walking + transit)
    # Add base time for waiting/transitions
    if distance_km < 0.5:
        # Very close, mostly walking
        travel_time_min = int(distance_km * 12)  # ~5 km/h walking
    elif distance_km < 2.0:
        # Walking distance
        travel_time_min = int(distance_km * 10) + 5  # ~6 km/h + buffer
    else:
        # Transit required
        travel_time_min = int(distance_km * 3) + 10  # ~20 km/h + wait time
    
    # Minimum 5 minutes, maximum 60 minutes
    travel_time_min = max(5, min(travel_time_min, 60))
    
    logger.debug(f"Distance: {distance_km:.2f} km, Travel time: {travel_time_min} min")
    
    return distance_km, travel_time_min
