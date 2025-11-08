"""
Booking link generation tools.

This module provides functions to generate booking links for flights and hotels.
"""

import logging
from typing import Dict
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


def build_flight_link(
    origin: str,
    destination: str,
    start_date: str,
    return_date: str = None
) -> str:
    """
    Generate a flight booking link.
    
    Args:
        origin: Origin city or airport code
        destination: Destination city or airport code
        start_date: Departure date in YYYY-MM-DD format
        return_date: Optional return date in YYYY-MM-DD format
        
    Returns:
        URL string for flight booking search
    """
    # Use Google Flights as the booking platform
    # Format: https://www.google.com/travel/flights?q=Flights%20from%20{origin}%20to%20{destination}%20on%20{date}
    
    if return_date:
        query = f"Flights from {origin} to {destination} on {start_date} returning {return_date}"
    else:
        query = f"Flights from {origin} to {destination} on {start_date}"
    
    params = {"q": query}
    url = f"https://www.google.com/travel/flights?{urlencode(params)}"
    
    logger.info(f"Generated flight link: {url}")
    return url


def build_hotel_link(
    city: str,
    check_in: str,
    nights: int,
    party: Dict[str, int]
) -> str:
    """
    Generate a hotel booking link.
    
    Args:
        city: Destination city
        check_in: Check-in date in YYYY-MM-DD format
        nights: Number of nights
        party: Party composition dict with adults, children, teens
        
    Returns:
        URL string for hotel booking search
    """
    # Use Google Hotels as the booking platform
    # Calculate total guests
    adults = party.get("adults", 1)
    children = party.get("children", 0)
    teens = party.get("teens", 0)
    
    # Teens count as adults for hotel booking
    total_adults = adults + teens
    
    query = f"Hotels in {city}"
    
    # Build URL with parameters
    params = {
        "q": query,
        "ts": "CAESABogCgIaABIaEhQKBwjZDxALGBQSBwjZDxALGBkYATICEAAqCQoFOgNVU0QaAA"  # Base parameter
    }
    
    url = f"https://www.google.com/travel/hotels?{urlencode(params)}"
    
    logger.info(f"Generated hotel link for {city}, {nights} nights, {total_adults} adults, {children} children")
    return url
