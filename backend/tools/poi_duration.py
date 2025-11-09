"""
POI duration calculation utilities.

This module provides functions to calculate realistic visit durations
for different types of POIs based on their tags and characteristics.
"""

import logging
from typing import List

logger = logging.getLogger(__name__)


def calculate_poi_duration(poi_name: str, tags: List[str], default_duration: int = 60) -> int:
    """
    Calculate realistic visit duration for a POI based on its type/tags.
    
    Args:
        poi_name: Name of the POI
        tags: List of tags describing the POI type
        default_duration: Default duration if no specific rule applies
        
    Returns:
        Duration in minutes
    """
    # Normalize tags to lowercase for matching
    tags_lower = [tag.lower() for tag in tags]
    poi_name_lower = poi_name.lower()
    
    # Duration rules based on POI type (in minutes)
    duration_rules = {
        # Long visits (2-4 hours)
        "museum": 120,
        "art_gallery": 120,
        "zoo": 180,
        "aquarium": 150,
        "theme_park": 240,
        "amusement_park": 240,
        "national_park": 180,
        "botanical_garden": 120,
        "palace": 120,
        "castle": 120,
        "cathedral": 90,
        "temple": 90,
        "shrine": 60,
        
        # Medium visits (1-1.5 hours)
        "historic_site": 75,
        "historic": 75,
        "monument": 60,
        "memorial": 60,
        "landmark": 60,
        "architecture": 60,
        "church": 60,
        "mosque": 60,
        "market": 90,
        "shopping": 90,
        "beach": 90,
        "lake": 75,
        
        # Short visits (30-45 minutes)
        "viewpoint": 30,
        "view": 30,
        "lookout": 30,
        "observation_deck": 45,
        "statue": 30,
        "fountain": 30,
        "square": 45,
        "plaza": 45,
        "park": 60,
        "garden": 60,
        
        # Food/dining (1-2 hours)
        "restaurant": 90,
        "food": 90,
        "cafe": 60,
        "food_market": 75,
        
        # Activities (varies)
        "tour": 120,
        "walking_tour": 120,
        "boat_tour": 90,
        "cruise": 120,
        "show": 120,
        "performance": 120,
        "sports": 150,
        "stadium": 180,
        
        # Special cases
        "caves": 120,
        "cave": 120,
        "island": 180,
        "bridge": 30,
    }
    
    # Check for specific keywords in POI name
    name_keywords = {
        "museum": 120,
        "gallery": 120,
        "zoo": 180,
        "aquarium": 150,
        "park": 60,
        "garden": 90,
        "palace": 120,
        "castle": 120,
        "cathedral": 90,
        "temple": 90,
        "beach": 90,
        "market": 90,
        "tower": 60,
        "bridge": 30,
        "statue": 30,
        "memorial": 60,
        "caves": 120,
        "island": 180,
        "stadium": 180,
    }
    
    # First, check POI name for keywords
    for keyword, duration in name_keywords.items():
        if keyword in poi_name_lower:
            logger.debug(f"POI '{poi_name}' matched name keyword '{keyword}' -> {duration} min")
            return duration
    
    # Collect all matching durations with priority scoring
    exact_matches = []
    compound_matches = []
    
    # First pass: Check for exact tag matches (highest priority)
    for tag in tags_lower:
        if tag in duration_rules:
            exact_matches.append((tag, duration_rules[tag]))
            logger.debug(f"POI '{poi_name}' exact match tag '{tag}' -> {duration_rules[tag]} min")
    
    # Second pass: Check for compound tags only if no exact matches
    # But be more careful to avoid false positives
    if not exact_matches:
        for tag in tags_lower:
            for rule_tag, duration in duration_rules.items():
                # Only match if it's a true compound (underscore separated)
                # Avoid substring matches like "park" in "theme_park"
                if "_" in rule_tag:
                    # For compound rules like "theme_park", check if tag contains the parts
                    if rule_tag in tag or tag in rule_tag:
                        compound_matches.append((rule_tag, duration))
                        logger.debug(f"POI '{poi_name}' compound match '{tag}' with '{rule_tag}' -> {duration} min")
    
    # Prioritize exact matches, then compound matches
    if exact_matches:
        # For exact matches, use intelligent selection based on POI type
        # If "view" is present, prioritize it (shorter duration)
        # If "museum" is present, prioritize it (longer duration)
        priority_tags = ["view", "viewpoint", "lookout", "observation_deck"]
        for tag, duration in exact_matches:
            if tag in priority_tags:
                logger.debug(f"POI '{poi_name}' prioritized view tag '{tag}' -> {duration} min")
                return duration
        
        # Otherwise, use the most appropriate duration (not always max)
        # For multiple matches, prefer the more specific/longer one
        selected = max(exact_matches, key=lambda x: x[1])
        logger.debug(f"POI '{poi_name}' selected from exact matches: {selected[0]} -> {selected[1]} min")
        return selected[1]
    
    elif compound_matches:
        # For compound matches, use the longest duration
        selected = max(compound_matches, key=lambda x: x[1])
        logger.debug(f"POI '{poi_name}' selected from compound matches: {selected[0]} -> {selected[1]} min")
        return selected[1]
    
    # Default duration
    logger.debug(f"POI '{poi_name}' using default duration -> {default_duration} min")
    return default_duration


def adjust_duration_for_party(base_duration: int, party: dict) -> int:
    """
    Adjust POI duration based on party composition.
    
    Families with children typically need more time.
    
    Args:
        base_duration: Base duration in minutes
        party: Party composition dict with adults, children, teens
        
    Returns:
        Adjusted duration in minutes
    """
    children = party.get("children", 0)
    
    # Add 20% more time if traveling with children
    if children > 0:
        adjusted = int(base_duration * 1.2)
        logger.debug(f"Adjusted duration for {children} children: {base_duration} -> {adjusted} min")
        return adjusted
    
    return base_duration


def adjust_duration_for_pace(base_duration: int, pace: str) -> int:
    """
    Adjust POI duration based on travel pace preference.
    
    Args:
        base_duration: Base duration in minutes
        pace: Travel pace ("relaxed", "moderate", "fast")
        
    Returns:
        Adjusted duration in minutes
    """
    pace_multipliers = {
        "relaxed": 1.3,   # 30% more time
        "moderate": 1.0,  # No change
        "fast": 0.8       # 20% less time
    }
    
    multiplier = pace_multipliers.get(pace, 1.0)
    adjusted = int(base_duration * multiplier)
    
    if multiplier != 1.0:
        logger.debug(f"Adjusted duration for '{pace}' pace: {base_duration} -> {adjusted} min")
    
    return adjusted
