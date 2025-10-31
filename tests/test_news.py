"""Tests for NewsAPI client."""
import pytest
from unittest.mock import Mock, patch
from requests.exceptions import HTTPError, Timeout

from app.services.news import NewsAPIClient


@pytest.fixture
def news_client():
    """Create NewsAPI client with mock API key."""
    return NewsAPIClient(api_key="test_api_key")


@patch("app.services.news.requests.Session.get")
def test_get_everything_success(mock_get, news_client, mock_newsapi_response):
    """Test successful article fetch."""
    mock_response = Mock()
    mock_response.json.return_value = mock_newsapi_response
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    result = news_client.get_everything("TSLA")

    assert result["status"] == "ok"
    assert len(result["articles"]) == 2
    mock_get.assert_called_once()


@patch("app.services.news.requests.Session.get")
def test_get_everything_http_error(mock_get, news_client):
    """Test HTTP error handling."""
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = HTTPError("404 Error")
    mock_get.return_value = mock_response

    with pytest.raises(HTTPError):
        news_client.get_everything("TSLA")


@patch("app.services.news.requests.Session.get")
def test_get_everything_timeout(mock_get, news_client):
    """Test timeout handling."""
    mock_get.side_effect = Timeout("Request timeout")

    with pytest.raises(Timeout):
        news_client.get_everything("TSLA")


@patch("app.services.news.requests.Session.get")
def test_get_everything_api_error_status(mock_get, news_client):
    """Test NewsAPI error status handling."""
    mock_response = Mock()
    mock_response.json.return_value = {"status": "error", "message": "API key invalid"}
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    with pytest.raises(HTTPError):
        news_client.get_everything("TSLA")


@patch("app.services.news.requests.Session.get")
def test_get_articles_for_stock(mock_get, news_client, mock_newsapi_response):
    """Test getting articles for stock symbol."""
    mock_response = Mock()
    mock_response.json.return_value = mock_newsapi_response
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    articles = news_client.get_articles_for_stock("TSLA", max_articles=10)

    assert len(articles) == 2
    assert articles[0]["title"] == "Tesla Reports Strong Q3 Earnings"


@patch("app.services.news.requests.Session.get")
def test_get_articles_for_stock_empty(mock_get, news_client, mock_empty_newsapi_response):
    """Test getting articles when none are found."""
    mock_response = Mock()
    mock_response.json.return_value = mock_empty_newsapi_response
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    articles = news_client.get_articles_for_stock("INVALID")

    assert len(articles) == 0
