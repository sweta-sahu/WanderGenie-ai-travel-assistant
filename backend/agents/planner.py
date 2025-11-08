"""
Planner Agent for the LangGraph travel planning workflow.

This agent is responsible for parsing natural language user input and
extracting structured travel intent (destination, dates, party, preferences).
"""

from langchain_core.messages import SystemMessage, HumanMessage
from .state import TripState, Intent
from .llm_config import llm_provider
import json
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = """You are a travel planning assistant specialized in parsing user travel requests.

Your task is to extract structured travel intent from natural language input.

Extract the following information:
- city: Destination city (e.g., "New York City, NY")
- origin: Origin city if mentioned (e.g., "Buffalo, NY") - use null if not mentioned
- start_date: Trip start date in YYYY-MM-DD format
- nights: Number of nights (calculate from duration if needed)
- party: Number of adults, children (0-12), and teens (13-17)
- prefs: Travel preferences including:
  - pace: "relaxed", "moderate", or "fast"
  - interests: List of interests (e.g., ["views", "food", "art", "history"])
  - constraints: List of constraints (e.g., ["avoid long walks", "no early mornings"])

Output ONLY valid JSON matching this schema:
{
  "city": "string",
  "origin": "string or null",
  "start_date": "YYYY-MM-DD",
  "nights": number,
  "party": {"adults": number, "children": number, "teens": number},
  "prefs": {
    "pace": "relaxed|moderate|fast",
    "interests": ["string"],
    "constraints": ["string"]
  }
}

Examples:
Input: "5 days in NYC from Buffalo, Dec 20-25, with a teen, love views & pizza"
Output: {
  "city": "New York City, NY",
  "origin": "Buffalo, NY",
  "start_date": "2025-12-20",
  "nights": 5,
  "party": {"adults": 2, "children": 0, "teens": 1},
  "prefs": {
    "pace": "moderate",
    "interests": ["views", "food"],
    "constraints": []
  }
}

Input: "Weekend in Paris, just me, love museums and cafes, taking it slow"
Output: {
  "city": "Paris, France",
  "origin": null,
  "start_date": "2025-11-15",
  "nights": 2,
  "party": {"adults": 1, "children": 0, "teens": 0},
  "prefs": {
    "pace": "relaxed",
    "interests": ["museums", "cafes", "art"],
    "constraints": []
  }
}

IMPORTANT: Return ONLY the JSON object, no additional text or explanation.
"""


def validate_intent_json(intent_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate the intent JSON structure and required fields.
    
    Args:
        intent_data: Parsed JSON data from LLM response
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Check required top-level fields
        required_fields = ["city", "start_date", "nights", "party", "prefs"]
        for field in required_fields:
            if field not in intent_data:
                return False, f"Missing required field: {field}"
        
        # Validate party composition
        party = intent_data.get("party", {})
        party_fields = ["adults", "children", "teens"]
        for field in party_fields:
            if field not in party:
                return False, f"Missing party field: {field}"
            if not isinstance(party[field], int) or party[field] < 0:
                return False, f"Invalid party.{field}: must be non-negative integer"
        
        # Validate preferences
        prefs = intent_data.get("prefs", {})
        if "pace" not in prefs:
            return False, "Missing prefs.pace field"
        if prefs["pace"] not in ["relaxed", "moderate", "fast"]:
            return False, f"Invalid pace: {prefs['pace']} (must be relaxed, moderate, or fast)"
        
        if "interests" not in prefs:
            return False, "Missing prefs.interests field"
        if not isinstance(prefs["interests"], list):
            return False, "prefs.interests must be a list"
        
        if "constraints" not in prefs:
            return False, "Missing prefs.constraints field"
        if not isinstance(prefs["constraints"], list):
            return False, "prefs.constraints must be a list"
        
        # Validate data types
        if not isinstance(intent_data["city"], str) or not intent_data["city"]:
            return False, "city must be a non-empty string"
        
        if not isinstance(intent_data["nights"], int) or intent_data["nights"] <= 0:
            return False, "nights must be a positive integer"
        
        # Validate date format (basic check)
        start_date = intent_data["start_date"]
        if not isinstance(start_date, str) or len(start_date) != 10:
            return False, "start_date must be in YYYY-MM-DD format"
        
        return True, None
        
    except Exception as e:
        return False, f"Validation error: {str(e)}"


def planner_node(state: TripState) -> TripState:
    """
    Planner agent: Parse user input into structured intent.
    
    This node extracts structured travel information from natural language
    user input, including destination, dates, party composition, and preferences.
    
    Args:
        state: Current TripState with user_input populated
        
    Returns:
        Updated TripState with intent populated or errors added
    """
    logger.info("Planner agent starting")
    
    try:
        # Prepare messages for LLM
        messages = [
            SystemMessage(content=PLANNER_SYSTEM_PROMPT),
            HumanMessage(content=state["user_input"])
        ]
        
        # Invoke LLM with fallback support
        logger.info("Invoking LLM to extract intent")
        response = llm_provider.invoke_with_fallback(messages)
        
        # Parse JSON response
        response_content = response.content.strip()
        logger.debug(f"LLM response: {response_content}")
        
        # Handle potential markdown code blocks
        if response_content.startswith("```"):
            # Extract JSON from code block
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
        
        intent_data = json.loads(response_content)
        
        # Validate intent structure
        is_valid, error_msg = validate_intent_json(intent_data)
        if not is_valid:
            logger.error(f"Intent validation failed: {error_msg}")
            state["errors"].append(f"Planner validation error: {error_msg}")
            state["status"] = "error"
            state["current_agent"] = "planner"
            return state
        
        # Update state with extracted intent
        state["intent"] = intent_data
        state["status"] = "planning_complete"
        state["current_agent"] = "planner"
        
        logger.info(f"Planner extracted intent for {intent_data['city']}, {intent_data['nights']} nights")
        logger.debug(f"Full intent: {json.dumps(intent_data, indent=2)}")
        
        return state
        
    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse LLM response as JSON: {str(e)}"
        logger.error(error_msg)
        logger.error(f"Response content: {response.content if 'response' in locals() else 'N/A'}")
        state["errors"].append(f"Planner JSON error: {error_msg}")
        state["status"] = "error"
        state["current_agent"] = "planner"
        return state
        
    except Exception as e:
        error_msg = f"Planner agent failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        state["errors"].append(error_msg)
        state["status"] = "error"
        state["current_agent"] = "planner"
        return state


EDIT_PLANNER_SYSTEM_PROMPT = """You are a travel planning assistant specialized in parsing edit instructions for existing trips.

You will receive:
1. The current trip intent (destination, dates, party, preferences)
2. An edit instruction from the user

Your task is to:
1. Parse the edit instruction to understand what the user wants to change
2. Identify which aspects of the intent need modification (dates, party, preferences, etc.)
3. Apply the changes to create an updated intent
4. Return the complete updated intent JSON

Output ONLY valid JSON with two fields:
{
  "edit_type": "intent_change|preference_change|no_change",
  "updated_intent": {
    "city": "string",
    "origin": "string or null",
    "start_date": "YYYY-MM-DD",
    "nights": number,
    "party": {"adults": number, "children": number, "teens": number},
    "prefs": {
      "pace": "relaxed|moderate|fast",
      "interests": ["string"],
      "constraints": ["string"]
    }
  }
}

Edit types:
- "intent_change": Major changes like dates, destination, party size
- "preference_change": Changes to pace, interests, or constraints only
- "no_change": Edit doesn't affect intent (e.g., "replace this POI with that POI")

Examples:

Input:
Current Intent: {"city": "NYC", "start_date": "2025-12-20", "nights": 5, ...}
Edit: "Change the trip to start on December 22 instead"
Output: {
  "edit_type": "intent_change",
  "updated_intent": {"city": "NYC", "start_date": "2025-12-22", "nights": 5, ...}
}

Input:
Current Intent: {"city": "Paris", "prefs": {"pace": "moderate", "interests": ["art", "food"]}}
Edit: "Add shopping to my interests"
Output: {
  "edit_type": "preference_change",
  "updated_intent": {"city": "Paris", "prefs": {"pace": "moderate", "interests": ["art", "food", "shopping"]}}
}

Input:
Current Intent: {"city": "Tokyo", ...}
Edit: "Replace the museum visit on day 2 with a temple"
Output: {
  "edit_type": "no_change",
  "updated_intent": {same as current intent}
}

IMPORTANT: Return ONLY the JSON object, no additional text or explanation.
"""


def edit_planner_node(state: TripState) -> TripState:
    """
    Edit planner agent: Parse edit instructions and update intent if needed.
    
    This node analyzes edit instructions to determine if the trip intent needs
    to be modified (e.g., date changes, party size changes, preference updates).
    
    Args:
        state: Current TripState with intent and edit_instruction populated
        
    Returns:
        Updated TripState with modified intent if applicable
    """
    logger.info("Edit planner agent starting")
    
    try:
        current_intent = state.get("intent")
        edit_instruction = state.get("edit_instruction", state.get("user_input", ""))
        
        if not current_intent:
            error_msg = "Cannot edit without existing intent"
            logger.error(error_msg)
            state["errors"].append(error_msg)
            state["status"] = "error"
            state["current_agent"] = "edit_planner"
            return state
        
        # Prepare messages for LLM
        messages = [
            SystemMessage(content=EDIT_PLANNER_SYSTEM_PROMPT),
            HumanMessage(content=f"""
Current Intent:
{json.dumps(current_intent, indent=2)}

Edit Instruction:
{edit_instruction}

Parse the edit instruction and return the updated intent.
""")
        ]
        
        # Invoke LLM with fallback support
        logger.info("Invoking LLM to parse edit instruction")
        response = llm_provider.invoke_with_fallback(messages)
        
        # Parse JSON response
        response_content = response.content.strip()
        logger.debug(f"LLM response: {response_content}")
        
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
        
        edit_data = json.loads(response_content)
        
        # Extract edit type and updated intent
        edit_type = edit_data.get("edit_type", "no_change")
        updated_intent = edit_data.get("updated_intent", current_intent)
        
        # Validate updated intent structure
        is_valid, error_msg = validate_intent_json(updated_intent)
        if not is_valid:
            logger.error(f"Updated intent validation failed: {error_msg}")
            state["errors"].append(f"Edit planner validation error: {error_msg}")
            state["status"] = "error"
            state["current_agent"] = "edit_planner"
            return state
        
        # Update state
        state["intent"] = updated_intent
        state["edit_type"] = edit_type
        state["status"] = "edit_planning_complete"
        state["current_agent"] = "edit_planner"
        
        logger.info(f"Edit planner completed: edit_type={edit_type}")
        logger.debug(f"Updated intent: {json.dumps(updated_intent, indent=2)}")
        
        return state
        
    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse LLM response as JSON: {str(e)}"
        logger.error(error_msg)
        logger.error(f"Response content: {response.content if 'response' in locals() else 'N/A'}")
        state["errors"].append(f"Edit planner JSON error: {error_msg}")
        state["status"] = "error"
        state["current_agent"] = "edit_planner"
        return state
        
    except Exception as e:
        error_msg = f"Edit planner agent failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        state["errors"].append(error_msg)
        state["status"] = "error"
        state["current_agent"] = "edit_planner"
        return state
