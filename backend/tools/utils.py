"""Utility tools for distance calculations and schema validation."""

import math
from typing import Any, Optional
from pydantic import ValidationError
from ..schemas.trip import POI
from ..utils.logger import get_logger

logger = get_logger(__name__)


def distance_calc(
    coord1: tuple[float, float],
    coord2: tuple[float, float]
) -> float:
    """
    Calculate distance between two coordinates using Haversine formula.
    
    The Haversine formula calculates the great-circle distance between two points
    on a sphere given their longitudes and latitudes. This is useful for calculating
    distances between POIs, determining proximity, and clustering locations.
    
    Args:
        coord1: (latitude, longitude) of first point in decimal degrees
        coord2: (latitude, longitude) of second point in decimal degrees
        
    Returns:
        Distance in kilometers (float)
        
    Raises:
        ValueError: If coordinates are invalid
        
    Example:
        # Distance between Statue of Liberty and Empire State Building
        distance = distance_calc((40.6892, -74.0445), (40.7484, -73.9857))
        # Returns approximately 8.8 km
        
        # Check if two POIs are within walking distance (< 1km)
        if distance_calc((poi1_lat, poi1_lon), (poi2_lat, poi2_lon)) < 1.0:
            print("Within walking distance")
    """
    try:
        # Validate coordinates
        lat1, lon1 = coord1
        lat2, lon2 = coord2
        
        # Check latitude bounds (-90 to 90)
        if not (-90 <= lat1 <= 90) or not (-90 <= lat2 <= 90):
            raise ValueError(
                f"Latitude must be between -90 and 90 degrees. "
                f"Got: lat1={lat1}, lat2={lat2}"
            )
        
        # Check longitude bounds (-180 to 180)
        if not (-180 <= lon1 <= 180) or not (-180 <= lon2 <= 180):
            raise ValueError(
                f"Longitude must be between -180 and 180 degrees. "
                f"Got: lon1={lon1}, lon2={lon2}"
            )
        
        # Earth's radius in kilometers
        R = 6371.0
        
        # Convert degrees to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2)
        
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        distance = R * c
        
        logger.debug(
            "distance_calculated",
            coord1=coord1,
            coord2=coord2,
            distance_km=distance
        )
        
        return distance
        
    except (TypeError, ValueError) as e:
        error_msg = f"Invalid coordinates: {str(e)}"
        logger.error(
            "distance_calc_error",
            coord1=coord1,
            coord2=coord2,
            error=str(e)
        )
        raise ValueError(error_msg) from e


def validate_schema(data: dict, schema_name: str = "trip") -> dict:
    """
    Validate data against Pydantic schema.
    
    This tool validates data structures against defined Pydantic models to ensure
    data integrity and catch errors early. Currently supports POI schema validation.
    
    Args:
        data: Data dictionary to validate
        schema_name: Schema name to validate against (default: "trip")
                    Supported: "poi", "trip"
        
    Returns:
        Dictionary with validation results:
        {
            "valid": bool,
            "errors": list[str],  # Empty if valid
            "validated_data": dict  # Cleaned/validated data if valid, None otherwise
        }
        
    Example:
        # Validate a POI object
        poi_data = {
            "id": "opentripmap:N123",
            "name": "Statue of Liberty",
            "lat": 40.6892,
            "lon": -74.0445,
            "city": "NYC",
            "tags": ["landmark", "monument"],
            "source": "opentripmap",
            "source_id": "N123"
        }
        
        result = validate_schema(poi_data, "poi")
        if result["valid"]:
            print("POI is valid!")
            validated_poi = result["validated_data"]
        else:
            print(f"Validation errors: {result['errors']}")
    """
    try:
        # Validate schema_name
        supported_schemas = ["poi", "trip"]
        if schema_name not in supported_schemas:
            return {
                "valid": False,
                "errors": [
                    f"Unsupported schema: '{schema_name}'. "
                    f"Supported schemas: {', '.join(supported_schemas)}"
                ],
                "validated_data": None
            }
        
        # Validate data is a dictionary
        if not isinstance(data, dict):
            return {
                "valid": False,
                "errors": [f"Data must be a dictionary, got {type(data).__name__}"],
                "validated_data": None
            }
        
        # Select schema model
        if schema_name == "poi":
            schema_model = POI
        elif schema_name == "trip":
            # Trip schema not yet implemented, return error
            return {
                "valid": False,
                "errors": ["Trip schema validation not yet implemented"],
                "validated_data": None
            }
        else:
            return {
                "valid": False,
                "errors": [f"Unknown schema: {schema_name}"],
                "validated_data": None
            }
        
        # Attempt validation
        try:
            validated_obj = schema_model(**data)
            
            # Convert back to dictionary
            validated_data = validated_obj.model_dump()
            
            logger.info(
                "schema_validation_success",
                schema_name=schema_name,
                data_keys=list(data.keys())
            )
            
            return {
                "valid": True,
                "errors": [],
                "validated_data": validated_data
            }
            
        except ValidationError as e:
            # Extract error messages
            errors = []
            for error in e.errors():
                field = ".".join(str(loc) for loc in error["loc"])
                message = error["msg"]
                error_type = error["type"]
                errors.append(f"{field}: {message} (type: {error_type})")
            
            logger.warning(
                "schema_validation_failed",
                schema_name=schema_name,
                errors=errors
            )
            
            return {
                "valid": False,
                "errors": errors,
                "validated_data": None
            }
        
    except Exception as e:
        error_msg = f"Validation error: {str(e)}"
        logger.error(
            "validate_schema_error",
            schema_name=schema_name,
            error=str(e)
        )
        
        return {
            "valid": False,
            "errors": [error_msg],
            "validated_data": None
        }
