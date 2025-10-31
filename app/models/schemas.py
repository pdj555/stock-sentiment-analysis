"""Pydantic models for API requests and responses."""
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class SentimentAnalysisRequest(BaseModel):
    """Request model for sentiment analysis."""

    stock_symbol: str = Field(
        ..., description="Stock ticker symbol (e.g., TSLA, AAPL)", min_length=1, max_length=10
    )
    max_articles: int = Field(
        default=20, description="Maximum number of articles to analyze", ge=1, le=100
    )

    @field_validator("stock_symbol")
    @classmethod
    def validate_stock_symbol(cls, v):
        """Validate and normalize stock symbol."""
        return v.strip().upper()


class ArticleSentiment(BaseModel):
    """Sentiment information for a single article."""

    title: str
    description: Optional[str] = None
    url: Optional[str] = None
    published_at: Optional[str] = None
    sentiment: str = Field(..., description="Sentiment classification: pos or neg")
    sentiment_score: int = Field(..., description="Sentiment score: 1 (positive) or -1 (negative)")


class SentimentAnalysisResponse(BaseModel):
    """Response model for sentiment analysis."""

    stock_symbol: str
    average_sentiment: float = Field(
        ..., description="Average sentiment score (-1.0 to 1.0)", ge=-1.0, le=1.0
    )
    total_articles: int = Field(..., ge=0)
    positive_articles: int = Field(..., ge=0)
    negative_articles: int = Field(..., ge=0)
    articles: List[ArticleSentiment] = Field(default_factory=list)

    model_config = {
        "json_schema_extra": {
            "example": {
                "stock_symbol": "TSLA",
                "average_sentiment": 0.65,
                "total_articles": 20,
                "positive_articles": 13,
                "negative_articles": 7,
                "articles": [
                    {
                        "title": "Tesla Reports Strong Q3 Earnings",
                        "description": "Tesla exceeded expectations...",
                        "url": "https://example.com/article",
                        "published_at": "2023-10-20T10:00:00Z",
                        "sentiment": "pos",
                        "sentiment_score": 1,
                    }
                ],
            }
        }
    }


class HealthCheckResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str
    nltk_data_available: bool
