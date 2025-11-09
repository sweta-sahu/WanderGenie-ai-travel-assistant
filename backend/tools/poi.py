"""POI search tool for discovering points of interest."""

import json
import logging
import os
import requests
from typing import List, Dict, Any, Optional
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

# OpenTripMap API
OPENTRIPMAP_API_KEY = os.getenv("OPENTRIPMAP_API_KEY", "")
OPENTRIPMAP_BASE_URL = "https://api.opentripmap.com/0.1/en/places"
# Tunables via env (with sensible defaults)
OPENTRIPMAP_RADIUS_METERS = int(os.getenv("OPENTRIPMAP_RADIUS_METERS", "8000"))
OPENTRIPMAP_DEFAULT_LIMIT = int(os.getenv("OPENTRIPMAP_LIMIT", "50"))
OPENTRIPMAP_KINDS = os.getenv(
    "OPENTRIPMAP_KINDS",
    "interesting_places,tourist_facilities,cultural,historic,architecture,natural,foods",
)

NYC_POIS_PATH = os.path.join(os.path.dirname(__file__), "../../data/nyc_pois.json")

# LLM import for fallback POI generation
_llm_provider = None


def load_nyc_fallback_data() -> List[Dict[str, Any]]:
    """Load hardcoded NYC POI data from JSON file."""
    try:
        with open(NYC_POIS_PATH, 'r') as f:
            pois = json.load(f)
        logger.info(f"Loaded {len(pois)} POIs from NYC fallback data")
        return pois
    except Exception as e:
        logger.error(f"Failed to load NYC fallback data: {e}")
        return []


def fetch_pois_from_opentripmap(city: str, limit: int = 30) -> List[Dict[str, Any]]:
    """
    Fetch POIs from OpenTripMap API.
    
    Args:
        city: City name (e.g., "Buffalo", "Boston")
        limit: Maximum number of POIs to return
        
    Returns:
        List of POI dictionaries
    """
    if not OPENTRIPMAP_API_KEY:
        logger.warning("OpenTripMap API key not configured")
        return []
    
    # Skip if city is clearly a state or country, not a city
    # OpenTripMap needs actual city names
    invalid_patterns = ['florida', 'california', 'texas', 'usa', 'united states']
    if any(pattern in city.lower() for pattern in invalid_patterns):
        logger.info(f"'{city}' appears to be a state/country, not a city - skipping OpenTripMap")
        return []
    
    try:
        # Step 1: Get city coordinates (geoname)
        # Try with full name first, then just city name
        geoname_url = f"{OPENTRIPMAP_BASE_URL}/geoname"
        
        # Try "City, State" format first
        for city_variant in [city, f"{city}, NY", f"{city}, USA"]:
            params = {"name": city_variant, "apikey": OPENTRIPMAP_API_KEY}
            response = requests.get(geoname_url, params=params, timeout=5)
            
            if response.status_code == 200:
                geo_data = response.json()
                if geo_data.get("status") != "NOT_FOUND" and geo_data.get("lat"):
                    break
        else:
            logger.info(f"City '{city}' not found in OpenTripMap")
            return []
        
        lat = geo_data.get("lat")
        lon = geo_data.get("lon")
        
        if not lat or not lon:
            logger.error(f"No coordinates for '{city}'")
            return []
        
        logger.info(f"Found coordinates for {city}: {lat}, {lon}")
        
        # Step 2: Search for POIs in configurable radius
        radius_url = f"{OPENTRIPMAP_BASE_URL}/radius"
        # Ensure we request enough results to meet caller's need
        requested_limit = max(limit, OPENTRIPMAP_DEFAULT_LIMIT)
        params = {
            "radius": OPENTRIPMAP_RADIUS_METERS,
            "lat": lat,
            "lon": lon,
            "kinds": OPENTRIPMAP_KINDS,
            "limit": requested_limit,
            "apikey": OPENTRIPMAP_API_KEY
        }
        
        response = requests.get(radius_url, params=params, timeout=10)
        if response.status_code != 200:
            logger.error(f"OpenTripMap radius search failed: {response.status_code}")
            return []
        
        places = response.json().get("features", [])
        logger.info(f"OpenTripMap returned {len(places)} places for {city}")
        
        # Step 3: Convert to our POI format
        pois = []
        for place in places[:requested_limit]:
            props = place.get("properties", {})
            geom = place.get("geometry", {}).get("coordinates", [])
            
            if len(geom) < 2:
                continue
            
            poi = {
                "name": props.get("name", "Unknown"),
                "lat": geom[1],
                "lon": geom[0],
                "tags": props.get("kinds", "").split(",")[:3],
                "duration_min": 60,  # Default
                "booking_required": False,
                "booking_url": None,
                "notes": "",
                "open_hours": None
            }
            pois.append(poi)
        
        logger.info(f"Converted {len(pois)} OpenTripMap POIs")
        return pois
        
    except requests.exceptions.Timeout:
        logger.error("OpenTripMap API timeout")
        return []
    except Exception as e:
        logger.error(f"OpenTripMap API error: {e}")
        return []


def check_cached_pois_in_vectordb(city: str, limit: int = 30) -> List[Dict[str, Any]]:
    """
    Check if we have previously generated/cached POIs for this city in VectorDB.
    
    Args:
        city: City name
        limit: Maximum POIs to retrieve
        
    Returns:
        List of cached POI dictionaries, or empty list if none found
    """
    try:
        from backend.memory.vectordb import VectorDBClient
        
        vectordb = VectorDBClient()
        vectordb.connect()
        
        # Query for POIs in this city using poi_facts table
        query = f"attractions and points of interest in {city}"
        
        results = vectordb.similarity_search(
            collection_name="poi_facts",
            query=query,
            k=limit,
            filters={"city": city}
        )
        
        # Convert VectorDB results to POI format
        pois = []
        for result in results:
            # Skip if not from this city (in case filters didn't work)
            if result.get("city", "").lower() != city.lower():
                continue
            
            # Parse coords from PostgreSQL point format "(lon,lat)"
            lat, lon = None, None
            coords = result.get("coords")
            if coords:
                try:
                    # coords is in format "(x,y)" or "(lon,lat)"
                    if isinstance(coords, str):
                        # Remove parentheses and split
                        coords_clean = coords.strip("()").split(",")
                        lon = float(coords_clean[0])
                        lat = float(coords_clean[1])
                    elif isinstance(coords, (list, tuple)) and len(coords) >= 2:
                        lon, lat = float(coords[0]), float(coords[1])
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse coords for {result.get('name')}: {e}")
                    continue
            
            if lat is None or lon is None:
                logger.warning(f"Skipping POI {result.get('name')} - missing coordinates")
                continue
                
            poi = {
                "name": result.get("name"),
                "lat": lat,
                "lon": lon,
                "tags": result.get("tags", []),
                "duration_min": 60,  # Default
                "booking_required": result.get("booking_required", False),
                "booking_url": result.get("booking_url"),
                "notes": result.get("hours_text", ""),
                "open_hours": result.get("hours_text")
            }
            pois.append(poi)
        
        if pois:
            logger.info(f"📦 Found {len(pois)} cached POIs for {city} in VectorDB")
        
        return pois
        
    except Exception as e:
        logger.debug(f"No cached POIs found in VectorDB for {city}: {e}")
        return []


def poi_search(city: str, interests: List[str], limit: int = 30) -> List[Dict[str, Any]]:
    """
    Search for POIs in a given city.
    
    Strategy:
    1. Check VectorDB cache (previously generated/saved POIs)
    2. Try OpenTripMap API for any city
    3. Fallback to hardcoded NYC data if API fails and city is NYC
    4. LLM fallback: Generate POIs using LLM and save to cache
    """
    logger.info(f"🔍 POI search for city: {city}, interests: {interests}")
    
    city_normalized = city.lower().strip()
    
    # First, check if we have cached POIs for this city
    logger.info("Checking VectorDB cache for existing POIs...")
    cached_pois = check_cached_pois_in_vectordb(city, limit=limit)
    
    if cached_pois and len(cached_pois) >= 15:
        logger.info(f"✅ Using {len(cached_pois)} cached POIs from VectorDB")
        return cached_pois[:limit]
    
    # Try OpenTripMap API
    logger.info("Trying OpenTripMap API...")
    api_pois = fetch_pois_from_opentripmap(city, limit=limit)
    
    if api_pois and len(api_pois) >= 15:
        logger.info(f"✅ OpenTripMap returned {len(api_pois)} POIs")
        return api_pois[:limit]
    
    # Fallback to NYC hardcoded data if city is NYC
    if any(term in city_normalized for term in ["new york", "nyc", "manhattan"]):
        logger.warning("OpenTripMap insufficient, using NYC fallback data")
        all_pois = load_nyc_fallback_data()
        
        if interests and len(interests) > 0:
            filtered_pois = []
            for poi in all_pois:
                poi_tags = set(tag.lower() for tag in poi.get("tags", []))
                interest_tags = set(interest.lower() for interest in interests)
                
                if poi_tags.intersection(interest_tags):
                    filtered_pois.append(poi)
            
            logger.info(f"Filtered {len(all_pois)} POIs to {len(filtered_pois)} matching interests")
            
            if len(filtered_pois) < 15:
                logger.warning(f"Only {len(filtered_pois)} POIs matched, returning all")
                return all_pois[:limit]
            
            return filtered_pois[:limit]
        
        return all_pois[:limit]
    
    # If we reach here, OpenTripMap returned insufficient POIs for a non-NYC city
    # Use LLM fallback to generate POIs
    logger.warning(f"⚠️  Insufficient POIs from OpenTripMap ({len(api_pois)}), trying LLM fallback...")
    llm_pois = generate_pois_with_llm(city, interests, limit=limit)
    
    if llm_pois and len(llm_pois) >= 15:
        logger.info(f"✅ LLM fallback generated {len(llm_pois)} POIs for {city}")
        return llm_pois[:limit]
    
    # Last resort: return whatever we got (even if insufficient)
    logger.error(f"❌ All sources failed for '{city}' (API: {len(api_pois)}, LLM: {len(llm_pois)})")
    
    # Combine what we got from both sources
    combined_pois = api_pois + llm_pois
    return combined_pois[:limit] if combined_pois else []


def save_pois_to_vectordb(city: str, pois: List[Dict[str, Any]]) -> bool:
    """
    Save LLM-generated POIs to VectorDB for future reuse.
    
    This builds up the knowledge base over time so we don't regenerate
    the same POIs for the same city multiple times.
    
    Args:
        city: City name
        pois: List of POI dictionaries to save
        
    Returns:
        True if save was successful, False otherwise
    """
    try:
        from backend.memory.vectordb import VectorDBClient
        import uuid
        
        # Create VectorDB client
        vectordb = VectorDBClient()
        vectordb.connect()
        
        # Convert POIs to documents for poi_facts table schema
        documents = []
        for poi in pois:
            # Create a rich text description for embedding
            tags_str = ", ".join(poi.get("tags", []))
            notes = poi.get("notes", "")
            body = f"{poi['name']} in {city}. Tags: {tags_str}. {notes if notes else 'A popular attraction.'}"
            
            # Convert lat/lon to PostgreSQL point format: "(lon,lat)"
            # Note: PostgreSQL point is (x,y) which maps to (lon,lat)
            coords_point = f"({poi['lon']},{poi['lat']})"
            
            # Generate a unique ID
            poi_id = f"llm_{city.lower().replace(' ', '_').replace(',', '')}_{poi['name'].lower().replace(' ', '_')[:30]}_{uuid.uuid4().hex[:8]}"
            
            doc = {
                "id": poi_id,
                "city": city,
                "name": poi["name"],
                "coords": coords_point,  # PostgreSQL point format
                "tags": poi.get("tags", []),
                "booking_required": poi.get("booking_required", False),
                "booking_url": poi.get("booking_url"),
                "hours_text": poi.get("notes", ""),  # Map notes to hours_text
                "popularity": 0.5,  # Default popularity for LLM-generated POIs
                "body": body  # For embedding generation
            }
            documents.append(doc)
        
        # Save to poi_facts table
        collection = "poi_facts"
        result = vectordb.insert_documents(collection, documents)
        
        if result["success"] > 0:
            logger.info(f"✅ Saved {result['success']}/{len(documents)} LLM-generated POIs to VectorDB ({collection}) for {city}")
            return True
        else:
            logger.warning(f"⚠️  Failed to save POIs to VectorDB: {result['errors']}")
            return False
            
    except Exception as e:
        logger.warning(f"Failed to save POIs to VectorDB (non-critical): {e}")
        # Don't fail the whole request if DB save fails
        return False


def generate_pois_with_llm(city: str, interests: List[str], limit: int = 25, save_to_db: bool = True) -> List[Dict[str, Any]]:
    """
    Generate POIs using LLM when all other data sources fail.
    
    This is a fallback mechanism that uses the LLM's world knowledge to
    generate realistic POIs for any city. The LLM will create POIs with:
    - Realistic names based on the city
    - Approximate lat/lon coordinates
    - Relevant tags matching user interests
    - Reasonable duration estimates
    
    After generation, POIs are saved to VectorDB for future reuse.
    
    Args:
        city: City name (e.g., "Buffalo, NY")
        interests: List of user interests (e.g., ["views", "food", "museums"])
        limit: Number of POIs to generate (default: 25)
        save_to_db: Whether to save generated POIs to VectorDB (default: True)
        
    Returns:
        List of generated POI dictionaries
    """
    global _llm_provider
    
    try:
        # Lazy import to avoid circular dependency
        if _llm_provider is None:
            from backend.agents.llm_config import llm_provider
            _llm_provider = llm_provider
        
        logger.info(f"🤖 Generating POIs with LLM for {city} (interests: {interests})")
        
        # Prepare prompt for LLM
        interests_str = ", ".join(interests) if interests else "general attractions"
        
        system_prompt = f"""You are a travel expert POI generator. Generate realistic points of interest for a city.

Your task is to generate {limit} realistic POIs (Points of Interest) for {city}.

User interests: {interests_str}

Requirements:
1. Generate a diverse mix of POIs matching the user's interests
2. Include realistic names of actual places (or plausible fictional ones if you don't know)
3. Provide approximate but realistic latitude/longitude coordinates for {city}
4. Add relevant tags (e.g., "museum", "food", "view", "park", "historic")
5. Set reasonable duration_min (30-180 minutes)
6. Indicate if booking_required (true/false)
7. Include brief notes if helpful

Output ONLY a valid JSON array with this exact format:
[
  {{
    "name": "string",
    "lat": number,
    "lon": number,
    "tags": ["string"],
    "duration_min": number,
    "booking_required": boolean,
    "booking_url": null,
    "notes": "string"
  }}
]

IMPORTANT: 
- Return EXACTLY {limit} POIs
- Use realistic coordinates for {city}
- Match the user's interests ({interests_str})
- Return ONLY the JSON array, no other text
- Ensure all POIs are unique and diverse"""

        user_prompt = f"Generate {limit} realistic POIs for {city} focusing on: {interests_str}"
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        # Invoke LLM
        logger.info("Invoking LLM to generate POIs...")
        response = _llm_provider.invoke_with_fallback(messages)
        
        # Parse JSON response
        response_content = response.content.strip()
        logger.debug(f"LLM response (first 300 chars): {response_content[:300]}")
        
        # Handle potential markdown code blocks
        if response_content.startswith("```"):
            lines = response_content.split("\n")
            json_lines = []
            in_code_block = False
            for line in lines:
                if line.startswith("```"):
                    in_code_block = not in_code_block
                    continue
                if in_code_block or (not line.startswith("```")):
                    json_lines.append(line)
            response_content = "\n".join(json_lines).strip()
        
        # Parse JSON
        generated_pois = json.loads(response_content)
        
        # Validate structure
        if not isinstance(generated_pois, list):
            logger.error("LLM did not return a list")
            return []
        
        # Ensure all POIs have required fields
        valid_pois = []
        required_fields = ["name", "lat", "lon", "tags", "duration_min", "booking_required"]
        
        for poi in generated_pois:
            if all(field in poi for field in required_fields):
                # Ensure open_hours field exists (set to None)
                poi["open_hours"] = None
                valid_pois.append(poi)
            else:
                logger.warning(f"Skipping invalid POI: {poi.get('name', 'unknown')}")
        
        logger.info(f"✅ LLM generated {len(valid_pois)} valid POIs for {city}")
        
        # Log sample POIs for debugging
        if valid_pois:
            sample_names = [poi['name'] for poi in valid_pois[:5]]
            logger.info(f"Sample POIs: {sample_names}")
        
        # Save to VectorDB for future reuse (knowledge base building)
        if save_to_db and valid_pois:
            logger.info(f"💾 Saving {len(valid_pois)} POIs to VectorDB for future reuse...")
            save_pois_to_vectordb(city, valid_pois)
        
        return valid_pois
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM POI response as JSON: {e}")
        logger.error(f"Response content: {response_content if 'response_content' in locals() else 'N/A'}")
        return []
    except Exception as e:
        logger.error(f"LLM POI generation failed: {e}", exc_info=True)
        return []


def get_open_hours(poi_id: str) -> Optional[Dict[str, Any]]:
    """Get operating hours for a POI."""
    logger.debug(f"get_open_hours called for {poi_id} (not implemented)")
    return None
