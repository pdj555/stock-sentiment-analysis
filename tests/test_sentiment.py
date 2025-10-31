"""Tests for sentiment analysis service."""
import pytest
from app.services.sentiment import SentimentAnalyzer


@pytest.fixture
def analyzer():
    """Create sentiment analyzer instance."""
    return SentimentAnalyzer()


def test_preprocess_text(analyzer):
    """Test text preprocessing."""
    text = "This is a test with some stopwords and the article"
    result = analyzer.preprocess_text(text)

    # Check that stopwords are removed
    assert "test" in result
    assert "is" not in result or "the" not in result  # Stopwords should be removed


def test_preprocess_empty_text(analyzer):
    """Test preprocessing empty text."""
    assert analyzer.preprocess_text("") == ""
    assert analyzer.preprocess_text(None) == ""


def test_get_sentiment_positive(analyzer):
    """Test sentiment analysis for positive text."""
    text = "This is amazing and wonderful! Great news!"
    result = analyzer.get_sentiment(text)

    assert "classification" in result
    assert result["classification"] in ["pos", "neg"]


def test_get_sentiment_negative(analyzer):
    """Test sentiment analysis for negative text."""
    text = "This is terrible and awful! Bad news!"
    result = analyzer.get_sentiment(text)

    assert "classification" in result
    assert result["classification"] in ["pos", "neg"]


def test_get_sentiment_empty(analyzer):
    """Test sentiment analysis for empty text."""
    result = analyzer.get_sentiment("")
    assert result["classification"] == "neutral"


def test_analyze_articles(analyzer):
    """Test analyzing multiple articles."""
    articles = [
        {
            "title": "Great news about Tesla",
            "description": "Tesla reports amazing earnings",
            "url": "https://example.com/1",
            "publishedAt": "2023-10-20T10:00:00Z",
        },
        {
            "title": "Bad news about Tesla",
            "description": "Tesla faces challenges",
            "url": "https://example.com/2",
            "publishedAt": "2023-10-19T15:00:00Z",
        },
    ]

    results = analyzer.analyze_articles(articles)

    assert len(results) == 2
    assert all(hasattr(r, "sentiment") for r in results)
    assert all(hasattr(r, "sentiment_score") for r in results)
    assert all(r.sentiment in ["pos", "neg"] for r in results)


def test_analyze_articles_empty(analyzer):
    """Test analyzing empty article list."""
    results = analyzer.analyze_articles([])
    assert len(results) == 0


def test_analyze_articles_no_content(analyzer):
    """Test analyzing articles without content."""
    articles = [{"title": None, "description": None}, {"title": "", "description": ""}]

    results = analyzer.analyze_articles(articles)
    # Articles without content should be skipped
    assert len(results) <= len(articles)
