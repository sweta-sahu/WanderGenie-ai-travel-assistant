"""
Booking link generation tools.

This module provides functions to generate booking links for flights and hotels.
Uses LLM web search for accurate, up-to-date booking links.
"""

import logging
from typing import Dict
from datetime import datetime, timedelta
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


def build_flight_link(
    origin: str,
    destination: str,
    start_date: str,
    return_date: str = None
) -> str:
    """
    Generate a flight booking link using LLM web search.
    
    Args:
        origin: Origin city or airport code
        destination: Destination city or airport code
        start_date: Departure date in YYYY-MM-DD format
        return_date: Optional return date in YYYY-MM-DD format
        
    Returns:
        URL string for flight booking search
    """
    try:
        # Try to use web search for accurate links
        from backend.tools.web_search import search_flight_booking_link
        
        if return_date:
            url = search_flight_booking_link(origin, destination, start_date, return_date)
        else:
            # If no return date, assume one-way
            url = search_flight_booking_link(origin, destination, start_date, start_date)
        
        logger.info(f"Generated flight link via web search: {url}")
        return url
        
    except Exception as e:
        logger.warning(f"Web search failed, using fallback: {e}")
        
        # Fallback to Google Flights
        if return_date:
            query = f"Flights from {origin} to {destination} on {start_date} returning {return_date}"
        else:
            query = f"Flights from {origin} to {destination} on {start_date}"
        
        params = {"q": query}
        url = f"https://www.google.com/travel/flights?{urlencode(params)}"
        
        logger.info(f"Generated flight link (fallback): {url}")
        return url


def build_hotel_link(
    city: str,
    check_in: str,
    nights: int,
    party: Dict[str, int]
) -> str:
    """
    Generate a hotel booking link using LLM web search.
    
    Args:
        city: Destination city
        check_in: Check-in date in YYYY-MM-DD format
        nights: Number of nights
        party: Party composition dict with adults, children, teens
        
    Returns:
        URL string for hotel booking search
    """
    try:
        # Calculate check-out date
        check_in_dt = datetime.strptime(check_in, "%Y-%m-%d")
        check_out_dt = check_in_dt + timedelta(days=nights)
        check_out = check_out_dt.strftime("%Y-%m-%d")
        
        # Calculate total guests
        adults = party.get("adults", 1)
        children = party.get("children", 0)
        teens = party.get("teens", 0)
        
        # Teens count as adults for hotel booking
        total_guests = adults + teens + children
        
        # Try to use web search for accurate links
        from backend.tools.web_search import search_hotel_booking_link
        
        url = search_hotel_booking_link(city, check_in, check_out, total_guests)
        
        logger.info(f"Generated hotel link via web search: {url}")
        return url
        
    except Exception as e:
        logger.warning(f"Web search failed, using fallback: {e}")
        
        # Fallback to Google Hotels
        query = f"Hotels in {city}"
        params = {"q": query}
        url = f"https://www.google.com/travel/hotels?{urlencode(params)}"
        
        logger.info(f"Generated hotel link (fallback): {url}")
        return url
