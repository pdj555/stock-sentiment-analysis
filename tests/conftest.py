"""Test configuration and fixtures."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_newsapi_response():
    """Mock NewsAPI response."""
    return {
        "status": "ok",
        "totalResults": 2,
        "articles": [
            {
                "title": "Tesla Reports Strong Q3 Earnings",
                "description": "Tesla exceeded expectations with record profits",
                "url": "https://example.com/article1",
                "publishedAt": "2023-10-20T10:00:00Z",
            },
            {
                "title": "Tesla Faces Production Challenges",
                "description": "Manufacturing issues slow down production",
                "url": "https://example.com/article2",
                "publishedAt": "2023-10-19T15:00:00Z",
            },
        ],
    }


@pytest.fixture
def mock_empty_newsapi_response():
    """Mock empty NewsAPI response."""
    return {"status": "ok", "totalResults": 0, "articles": []}
