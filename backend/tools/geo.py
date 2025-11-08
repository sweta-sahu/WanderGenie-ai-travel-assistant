"""
Geographic data tools.

This module provides functions to generate GeoJSON for map visualization.
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def make_geojson(days: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate GeoJSON FeatureCollection from itinerary days.
    
    Creates a GeoJSON object with:
    - Point features for each POI
    - LineString features connecting POIs in sequence
    
    Args:
        days: List of Day objects with blocks containing POIs
        
    Returns:
        GeoJSON FeatureCollection dictionary
    """
    features = []
    
    # Track all coordinates for route line
    all_coordinates = []
    
    # Process each day
    for day_idx, day in enumerate(days):
        date = day.get("date", "")
        blocks = day.get("blocks", [])
        
        # Process each block (POI visit)
        for block_idx, block in enumerate(blocks):
            poi = block.get("poi", {})
            
            # Skip lunch breaks or blocks without POI
            if not poi or not poi.get("name"):
                continue
            
            lat = poi.get("lat")
            lon = poi.get("lon")
            
            if lat is None or lon is None:
                logger.warning(f"POI {poi.get('name')} missing coordinates")
                continue
            
            # Add POI as a point feature
            point_feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [lon, lat]  # GeoJSON uses [lon, lat]
                },
                "properties": {
                    "name": poi.get("name", "Unknown"),
                    "day": day_idx + 1,
                    "date": date,
                    "start_time": block.get("start_time", ""),
                    "end_time": block.get("end_time", ""),
                    "duration_min": poi.get("duration_min", 0),
                    "tags": poi.get("tags", []),
                    "notes": poi.get("notes", ""),
                    "booking_required": poi.get("booking_required", False),
                    "booking_url": poi.get("booking_url", ""),
                    "marker_color": _get_day_color(day_idx),
                    "marker_symbol": str(block_idx + 1)
                }
            }
            features.append(point_feature)
            
            # Add to route coordinates
            all_coordinates.append([lon, lat])
    
    # Add route line connecting all POIs
    if len(all_coordinates) > 1:
        route_feature = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": all_coordinates
            },
            "properties": {
                "name": "Route",
                "stroke": "#3b82f6",
                "stroke-width": 3,
                "stroke-opacity": 0.7
            }
        }
        features.append(route_feature)
    
    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    
    logger.info(f"Generated GeoJSON with {len(features)} features")
    return geojson


def _get_day_color(day_index: int) -> str:
    """
    Get a color for a specific day index.
    
    Args:
        day_index: Zero-based day index
        
    Returns:
        Hex color string
    """
    colors = [
        "#ef4444",  # red
        "#f59e0b",  # amber
        "#10b981",  # emerald
        "#3b82f6",  # blue
        "#8b5cf6",  # violet
        "#ec4899",  # pink
        "#06b6d4",  # cyan
    ]
    return colors[day_index % len(colors)]
