"""
Pydantic schemas for API request bodies
"""
from pydantic import BaseModel, Field


class CreateTripRequest(BaseModel):
    """Request body for creating a new trip"""
    prompt: str = Field(
        ..., 
        description="Natural language travel request",
        example="5 days in NYC from Buffalo, Dec 20-25, with a teen, love views and pizza"
    )


class EditTripRequest(BaseModel):
    """Request body for editing an existing trip"""
    instruction: str = Field(
        ...,
        description="Natural language edit instruction",
        example="Swap Day 2 afternoon for MoMA"
    )

