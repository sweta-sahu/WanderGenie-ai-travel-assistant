"""
WanderGenie API - Main FastAPI application
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create FastAPI app
app = FastAPI(
    title="WanderGenie API",
    description="AI-powered travel planning assistant",
    version="1.0.0"
)

# CORS middleware - allow frontend to call our API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local development
        "http://localhost:3001",
        "https://*.vercel.app",   # Production frontend (when deployed)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "WanderGenie API",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "api": "ok",
        # Will add more checks later (DB, LLM, etc.)
    }


# Import and include routers
from backend.routes.trips import router as trips_router
app.include_router(trips_router)

