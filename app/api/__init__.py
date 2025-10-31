"""API package initialization."""
from fastapi import APIRouter
from app.api import sentiment, health

# Create main API router
api_router = APIRouter()

# Include sub-routers
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(sentiment.router, prefix="/sentiment", tags=["Sentiment Analysis"])

__all__ = ["api_router"]
