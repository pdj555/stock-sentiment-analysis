"""Tests for API endpoints."""
from unittest.mock import patch

from fastapi import status


def test_root_endpoint(client):
    """Test root endpoint returns welcome message."""
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "message" in data
    assert "version" in data
    assert "docs" in data


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "nltk_data_available" in data


@patch("app.services.news.NewsAPIClient.get_articles_for_stock")
@patch("app.services.sentiment.SentimentAnalyzer.analyze_articles")
def test_analyze_sentiment_success(mock_analyze, mock_get_articles, client, mock_newsapi_response):
    """Test successful sentiment analysis."""
    # Mock responses
    mock_get_articles.return_value = mock_newsapi_response["articles"]

    from app.models import ArticleSentiment

    mock_analyze.return_value = [
        ArticleSentiment(
            title="Tesla Reports Strong Q3 Earnings",
            description="Tesla exceeded expectations",
            sentiment="pos",
            sentiment_score=1,
        ),
        ArticleSentiment(
            title="Tesla Faces Production Challenges",
            description="Manufacturing issues",
            sentiment="neg",
            sentiment_score=-1,
        ),
    ]

    # Make request
    response = client.post("/sentiment/analyze", json={"stock_symbol": "TSLA", "max_articles": 20})

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["stock_symbol"] == "TSLA"
    assert data["total_articles"] == 2
    assert data["positive_articles"] == 1
    assert data["negative_articles"] == 1
    assert data["average_sentiment"] == 0.0
    assert len(data["articles"]) == 2


@patch("app.services.news.NewsAPIClient.get_articles_for_stock")
def test_analyze_sentiment_no_articles(mock_get_articles, client):
    """Test sentiment analysis with no articles found."""
    mock_get_articles.return_value = []

    response = client.post(
        "/sentiment/analyze", json={"stock_symbol": "INVALID", "max_articles": 20}
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "No articles found" in response.json()["detail"]


def test_analyze_sentiment_invalid_symbol(client):
    """Test sentiment analysis with invalid stock symbol."""
    response = client.post("/sentiment/analyze", json={"stock_symbol": "", "max_articles": 20})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_analyze_sentiment_invalid_max_articles(client):
    """Test sentiment analysis with invalid max_articles."""
    response = client.post("/sentiment/analyze", json={"stock_symbol": "TSLA", "max_articles": 0})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    response = client.post("/sentiment/analyze", json={"stock_symbol": "TSLA", "max_articles": 150})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@patch("app.services.news.NewsAPIClient.get_articles_for_stock")
def test_analyze_sentiment_api_error(mock_get_articles, client):
    """Test sentiment analysis when NewsAPI fails."""
    from requests.exceptions import RequestException

    mock_get_articles.side_effect = RequestException("API Error")

    response = client.post("/sentiment/analyze", json={"stock_symbol": "TSLA", "max_articles": 20})

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
