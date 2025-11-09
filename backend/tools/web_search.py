"""
Web search tool for finding accurate booking links and information.

This module uses LLM with web search capabilities to find real, accurate
booking links for flights, hotels, and POI bookings.
"""

import logging
from typing import Optional, Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependency
_llm_provider = None


def search_flight_booking_link(origin: str, destination: str, start_date: str, return_date: str) -> str:
    """
    Use LLM with web search to find the best flight booking link.
    
    Args:
        origin: Origin city
        destination: Destination city
        start_date: Departure date (YYYY-MM-DD)
        return_date: Return date (YYYY-MM-DD)
        
    Returns:
        URL string for flight booking
    """
    global _llm_provider
    
    try:
        if _llm_provider is None:
            from backend.agents.llm_config import llm_provider
            _llm_provider = llm_provider
        
        system_prompt = """You are a travel booking assistant. Your task is to provide accurate booking links.

When asked for a flight booking link, search the web for the best flight booking platforms and return a properly formatted URL.

Prefer these platforms in order:
1. Google Flights (https://www.google.com/travel/flights)
2. Kayak (https://www.kayak.com/flights)
3. Skyscanner (https://www.skyscanner.com)

Return ONLY the URL, nothing else. The URL should be properly formatted with all necessary parameters."""

        user_prompt = f"""Find a flight booking link from {origin} to {destination}, departing {start_date} and returning {return_date}.

Search the web for the correct URL format and return a working booking link."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        logger.info(f"Searching web for flight link: {origin} -> {destination}")
        response = _llm_provider.invoke_with_fallback(messages)
        
        url = response.content.strip()
        
        # Clean up the response (remove markdown, quotes, etc.)
        url = url.replace("```", "").replace("`", "").replace('"', "").replace("'", "").strip()
        
        # If LLM didn't return a URL, fall back to Google Flights
        if not url.startswith("http"):
            from urllib.parse import urlencode
            query = f"Flights from {origin} to {destination} on {start_date} returning {return_date}"
            params = {"q": query}
            url = f"https://www.google.com/travel/flights?{urlencode(params)}"
        
        logger.info(f"Generated flight link: {url}")
        return url
        
    except Exception as e:
        logger.error(f"Web search for flight link failed: {e}")
        # Fallback to Google Flights
        from urllib.parse import urlencode
        query = f"Flights from {origin} to {destination} on {start_date} returning {return_date}"
        params = {"q": query}
        return f"https://www.google.com/travel/flights?{urlencode(params)}"


def search_hotel_booking_link(city: str, check_in: str, check_out: str, guests: int) -> str:
    """
    Use LLM with web search to find the best hotel booking link.
    
    Args:
        city: Destination city
        check_in: Check-in date (YYYY-MM-DD)
        check_out: Check-out date (YYYY-MM-DD)
        guests: Number of guests
        
    Returns:
        URL string for hotel booking
    """
    global _llm_provider
    
    try:
        if _llm_provider is None:
            from backend.agents.llm_config import llm_provider
            _llm_provider = llm_provider
        
        system_prompt = """You are a travel booking assistant. Your task is to provide accurate booking links.

When asked for a hotel booking link, search the web for the best hotel booking platforms and return a properly formatted URL.

Prefer these platforms in order:
1. Google Hotels (https://www.google.com/travel/hotels)
2. Booking.com (https://www.booking.com)
3. Hotels.com (https://www.hotels.com)

Return ONLY the URL, nothing else. The URL should be properly formatted with all necessary parameters."""

        user_prompt = f"""Find a hotel booking link for {city}, check-in {check_in}, check-out {check_out}, for {guests} guests.

Search the web for the correct URL format and return a working booking link."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        logger.info(f"Searching web for hotel link: {city}, {check_in} to {check_out}")
        response = _llm_provider.invoke_with_fallback(messages)
        
        url = response.content.strip()
        
        # Clean up the response
        url = url.replace("```", "").replace("`", "").replace('"', "").replace("'", "").strip()
        
        # If LLM didn't return a URL, fall back to Google Hotels
        if not url.startswith("http"):
            from urllib.parse import urlencode
            query = f"Hotels in {city}"
            params = {"q": query}
            url = f"https://www.google.com/travel/hotels?{urlencode(params)}"
        
        logger.info(f"Generated hotel link: {url}")
        return url
        
    except Exception as e:
        logger.error(f"Web search for hotel link failed: {e}")
        # Fallback to Google Hotels
        from urllib.parse import urlencode
        query = f"Hotels in {city}"
        params = {"q": query}
        return f"https://www.google.com/travel/hotels?{urlencode(params)}"


def search_poi_booking_link(poi_name: str, city: str) -> Optional[str]:
    """
    Use LLM with web search to find booking link for a specific POI.
    
    Args:
        poi_name: Name of the POI
        city: City where POI is located
        
    Returns:
        URL string for POI booking, or None if not found
    """
    global _llm_provider
    
    try:
        if _llm_provider is None:
            from backend.agents.llm_config import llm_provider
            _llm_provider = llm_provider
        
        system_prompt = """You are a travel booking assistant. Your task is to find official booking or ticket links for attractions.

When asked for a POI booking link, search the web for:
1. Official website with online booking
2. Third-party booking platforms (GetYourGuide, Viator, TripAdvisor)
3. Official ticketing systems

Return ONLY the URL if you find one, or "NONE" if no booking is required or available.
Do not make up URLs - only return real, working links."""

        user_prompt = f"""Find the official booking or ticket link for "{poi_name}" in {city}.

Search the web and return the URL if booking is available, or "NONE" if it's free entry or no booking required."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        logger.info(f"Searching web for POI booking link: {poi_name} in {city}")
        response = _llm_provider.invoke_with_fallback(messages)
        
        url = response.content.strip()
        
        # Clean up the response
        url = url.replace("```", "").replace("`", "").replace('"', "").replace("'", "").strip()
        
        if url.upper() == "NONE" or not url.startswith("http"):
            return None
        
        logger.info(f"Found POI booking link: {url}")
        return url
        
    except Exception as e:
        logger.error(f"Web search for POI booking link failed: {e}")
        return None
