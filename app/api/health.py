"""Health check and monitoring endpoints."""
from fastapi import APIRouter, status
import nltk

from app.models import HealthCheckResponse
from app.core import settings

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check",
    description="Check if the service is healthy and dependencies are available",
)
async def health_check() -> HealthCheckResponse:
    """
    Health check endpoint.

    Returns:
        Health status of the service
    """
    # Check if NLTK data is available
    nltk_data_available = True
    try:
        from nltk.corpus import stopwords

        stopwords.words("english")
        nltk.data.find("corpora/movie_reviews")
    except LookupError:
        nltk_data_available = False

    return HealthCheckResponse(
        status="healthy", version=settings.app_version, nltk_data_available=nltk_data_available
    )


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    summary="Root endpoint",
    description="Welcome message and API information",
)
async def root():
    """Root endpoint with API information."""
    return {
        "message": f"Welcome to {settings.app_name}",
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
    }
