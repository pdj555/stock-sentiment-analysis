"""Main FastAPI application."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core import settings, logger
from app.api import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    """
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Debug mode: {settings.debug}")

    # Initialize NLTK data
    from app.services.sentiment import sentiment_analyzer

    sentiment_analyzer._ensure_nltk_data()

    yield

    # Shutdown
    logger.info(f"Shutting down {settings.app_name}")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
    ## Stock Sentiment Analysis API

    A production-ready REST API for analyzing sentiment of news articles
    related to stock symbols.

    ### Features
    - Fetch latest news articles for any stock symbol
    - Sentiment analysis using NLTK and TextBlob
    - Detailed article-level sentiment scores
    - Average sentiment calculation
    - Comprehensive error handling and logging

    ### Usage
    1. Use the `/sentiment/analyze` endpoint to analyze stock sentiment
    2. Provide a stock symbol (e.g., TSLA, AAPL)
    3. Receive detailed sentiment analysis results
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Handle all uncaught exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500, content={"detail": "Internal server error", "type": type(exc).__name__}
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
