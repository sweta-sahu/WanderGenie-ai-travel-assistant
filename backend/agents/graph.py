"""
LangGraph workflow for multi-agent travel planning.

This module defines the state graph that orchestrates the Planner, Researcher,
and Packager agents in sequence, with state persistence via PostgreSQL checkpointer.
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from .state import TripState
from .planner import planner_node, edit_planner_node
from .researcher import researcher_node, edit_researcher_node
from .packager import packager_node, edit_packager_node
import os
import logging

logger = logging.getLogger(__name__)


def create_trip_graph():
    """
    Create the LangGraph workflow for trip planning.
    
    This function initializes a StateGraph with the TripState schema and adds
    three agent nodes (planner, researcher, packager) that execute sequentially.
    State is persisted to PostgreSQL after each agent execution via checkpointer.
    
    Returns:
        Compiled LangGraph application with checkpointer
        
    Raises:
        RuntimeError: If database connection string is not configured
    """
    logger.info("Creating LangGraph workflow for trip planning")
    
    # Initialize state graph with TripState schema
    workflow = StateGraph(TripState)
    
    # Add agent nodes
    logger.info("Adding agent nodes to workflow")
    workflow.add_node("planner", planner_node)
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("packager", packager_node)
    
    # Define sequential edges: planner → researcher → packager → END
    logger.info("Defining workflow edges")
    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "researcher")
    workflow.add_edge("researcher", "packager")
    workflow.add_edge("packager", END)
    
    # For MVP/hackathon: compile without checkpointer for simplicity
    # State persistence can be added later if needed
    logger.info("Compiling workflow without checkpointer (MVP mode)")
    app = workflow.compile()
    logger.info("LangGraph workflow compiled successfully")
    return app


def create_edit_graph():
    """
    Create the LangGraph workflow for editing existing trips.
    
    This function initializes a StateGraph for the edit workflow that:
    1. Loads existing trip state from database
    2. Parses edit instructions (edit_planner)
    3. Finds replacement POIs if needed (edit_researcher)
    4. Updates affected schedule portions (edit_packager)
    
    Returns:
        Compiled LangGraph application with checkpointer
        
    Raises:
        RuntimeError: If database connection string is not configured
    """
    logger.info("Creating LangGraph edit workflow")
    
    # Initialize state graph with TripState schema
    workflow = StateGraph(TripState)
    
    # Add edit agent nodes
    logger.info("Adding edit agent nodes to workflow")
    workflow.add_node("edit_planner", edit_planner_node)
    workflow.add_node("edit_researcher", edit_researcher_node)
    workflow.add_node("edit_packager", edit_packager_node)
    
    # Define sequential edges: edit_planner → edit_researcher → edit_packager → END
    logger.info("Defining edit workflow edges")
    workflow.set_entry_point("edit_planner")
    workflow.add_edge("edit_planner", "edit_researcher")
    workflow.add_edge("edit_researcher", "edit_packager")
    workflow.add_edge("edit_packager", END)
    
    # For MVP/hackathon: compile without checkpointer for simplicity
    logger.info("Compiling edit workflow without checkpointer (MVP mode)")
    app = workflow.compile()
    logger.info("LangGraph edit workflow compiled successfully")
    return app


# Global graph instances
# These are initialized when the module is imported
try:
    trip_graph = create_trip_graph()
    logger.info("Global trip_graph instance created")
except Exception as e:
    logger.error(f"Failed to create trip_graph: {e}")
    trip_graph = None

try:
    edit_graph = create_edit_graph()
    logger.info("Global edit_graph instance created")
except Exception as e:
    logger.error(f"Failed to create edit_graph: {e}")
    edit_graph = None
