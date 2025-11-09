"""
Calendar export tools.

This module provides functions to generate calendar export data (iCal format).
"""

import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def export_calendar(days: List[Dict[str, Any]], intent: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate calendar export data in iCal format.
    
    Creates calendar events for each POI visit in the itinerary.
    
    Args:
        days: List of Day objects with blocks containing POIs
        intent: Intent object with trip metadata
        
    Returns:
        Dictionary with iCal data and metadata
    """
    events = []
    
    city = intent.get("city", "Unknown City")
    
    # Process each day
    for day in days:
        date_str = day.get("date", "")
        blocks = day.get("blocks", [])
        
        # Parse date
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            logger.warning(f"Invalid date format: {date_str}")
            continue
        
        # Process each block
        for block in blocks:
            poi = block.get("poi", {})
            
            # Skip blocks without POI
            if not poi or not poi.get("name"):
                continue
            
            start_time = block.get("start_time", "09:00")
            end_time = block.get("end_time", "10:00")
            
            # Parse times
            try:
                start_hour, start_min = map(int, start_time.split(":"))
                end_hour, end_min = map(int, end_time.split(":"))
            except (ValueError, AttributeError):
                logger.warning(f"Invalid time format: {start_time} - {end_time}")
                continue
            
            # Create datetime objects
            start_dt = date_obj.replace(hour=start_hour, minute=start_min)
            end_dt = date_obj.replace(hour=end_hour, minute=end_min)
            
            # Create event
            event = {
                "summary": poi.get("name", "Unknown POI"),
                "location": f"{poi.get('name', '')}, {city}",
                "description": _build_event_description(poi, block),
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
                "geo": {
                    "lat": poi.get("lat"),
                    "lon": poi.get("lon")
                } if poi.get("lat") and poi.get("lon") else None
            }
            events.append(event)
    
    # Generate iCal string
    ical_string = _generate_ical_string(events, intent)
    
    result = {
        "format": "ical",
        "events_count": len(events),
        "ical_data": ical_string,
        "download_filename": f"trip_{city.replace(' ', '_').replace(',', '')}.ics"
    }
    
    logger.info(f"Generated calendar export with {len(events)} events")
    return result


def _build_event_description(poi: Dict[str, Any], block: Dict[str, Any]) -> str:
    """
    Build event description from POI and block data.
    
    Args:
        poi: POI dictionary
        block: Time block dictionary
        
    Returns:
        Event description string
    """
    parts = []
    
    # Add tags
    tags = poi.get("tags", [])
    if tags:
        parts.append(f"Tags: {', '.join(tags)}")
    
    # Add notes
    notes = poi.get("notes")
    if notes:
        parts.append(f"Notes: {notes}")
    
    # Add booking info
    if poi.get("booking_required"):
        parts.append("⚠️ Booking required")
        booking_url = poi.get("booking_url")
        if booking_url:
            parts.append(f"Book at: {booking_url}")
    
    # Add open hours
    open_hours = poi.get("open_hours")
    if open_hours:
        parts.append(f"Hours: {open_hours}")
    
    # Add travel time
    travel_time = block.get("travel_from_previous", 0)
    if travel_time > 0:
        parts.append(f"Travel time from previous: {travel_time} min")
    
    return "\n".join(parts)


def _generate_ical_string(events: List[Dict[str, Any]], intent: Dict[str, Any]) -> str:
    """
    Generate iCal format string from events.
    
    Args:
        events: List of event dictionaries
        intent: Intent object with trip metadata
        
    Returns:
        iCal format string
    """
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Travel Planner//EN",
        f"X-WR-CALNAME:Trip to {intent.get('city', 'Unknown')}",
        "X-WR-TIMEZONE:UTC",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH"
    ]
    
    for event in events:
        # Format datetime for iCal (remove separators and add Z for UTC)
        start_dt = datetime.fromisoformat(event["start"])
        end_dt = datetime.fromisoformat(event["end"])
        
        start_ical = start_dt.strftime("%Y%m%dT%H%M%S")
        end_ical = end_dt.strftime("%Y%m%dT%H%M%S")
        
        # Escape newlines in description for iCal format
        description_escaped = event['description'].replace('\n', '\\n')
        summary_escaped = event['summary'].replace(' ', '-')
        
        lines.extend([
            "BEGIN:VEVENT",
            f"DTSTART:{start_ical}",
            f"DTEND:{end_ical}",
            f"SUMMARY:{event['summary']}",
            f"LOCATION:{event['location']}",
            f"DESCRIPTION:{description_escaped}",
            f"UID:{start_ical}-{summary_escaped}@travelplanner.com",
            "STATUS:CONFIRMED",
            "SEQUENCE:0",
            "END:VEVENT"
        ])
    
    lines.append("END:VCALENDAR")
    
    return "\n".join(lines)
