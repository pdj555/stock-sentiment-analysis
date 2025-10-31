"""Sentiment analysis service using NLTK and TextBlob."""
import logging
from typing import List, Dict, Any
from nltk.corpus import stopwords
from textblob import TextBlob
from textblob.sentiments import NaiveBayesAnalyzer

from app.models import ArticleSentiment


class SentimentAnalyzer:
    """Service for analyzing text sentiment."""

    def __init__(self):
        """Initialize sentiment analyzer."""
        self.logger = logging.getLogger(__name__)
        self._ensure_nltk_data()

    def _ensure_nltk_data(self):
        """Ensure required NLTK data is downloaded."""
        import nltk

        try:
            stopwords.words("english")
        except LookupError:
            self.logger.info("Downloading NLTK stopwords...")
            nltk.download("stopwords", quiet=True)

        # Download movie_reviews for NaiveBayesAnalyzer
        try:
            nltk.data.find("corpora/movie_reviews")
        except LookupError:
            self.logger.info("Downloading NLTK movie_reviews corpus...")
            nltk.download("movie_reviews", quiet=True)

        # Download punkt for tokenization
        try:
            nltk.data.find("tokenizers/punkt")
        except LookupError:
            self.logger.info("Downloading NLTK punkt tokenizer...")
            nltk.download("punkt", quiet=True)

    def preprocess_text(self, text: str) -> str:
        """
        Preprocess text by removing stopwords.

        Args:
            text: Input text to preprocess

        Returns:
            Preprocessed text with stopwords removed
        """
        if not text:
            return ""

        try:
            blob = TextBlob(text)
            stop_words = set(stopwords.words("english"))
            tokens = [word for word in blob.words if word.lower() not in stop_words]
            return " ".join(tokens)
        except Exception as e:
            self.logger.error(f"Error preprocessing text: {e}")
            return text

    def get_sentiment(self, text: str) -> Dict[str, Any]:
        """
        Analyze sentiment of text.

        Args:
            text: Text to analyze

        Returns:
            Dictionary with sentiment classification and confidence
        """
        if not text:
            return {"classification": "neutral", "confidence": 0.0}

        try:
            blob = TextBlob(text, analyzer=NaiveBayesAnalyzer())
            classification = blob.sentiment.classification
            p_pos = blob.sentiment.p_pos
            p_neg = blob.sentiment.p_neg

            return {
                "classification": classification,
                "p_pos": p_pos,
                "p_neg": p_neg,
                "confidence": max(p_pos, p_neg),
            }
        except Exception as e:
            self.logger.error(f"Error analyzing sentiment: {e}")
            return {"classification": "neutral", "confidence": 0.0}

    def analyze_articles(self, articles: List[Dict[str, Any]]) -> List[ArticleSentiment]:
        """
        Analyze sentiment for multiple articles.

        Args:
            articles: List of article dictionaries from NewsAPI

        Returns:
            List of ArticleSentiment objects
        """
        analyzed_articles = []

        for article in articles:
            try:
                title = article.get("title", "")
                description = article.get("description", "")

                # Skip articles without content
                if not title and not description:
                    continue

                # Combine and preprocess text
                text = " ".join(filter(None, [title, description]))
                preprocessed_text = self.preprocess_text(text)

                # Get sentiment
                sentiment_result = self.get_sentiment(preprocessed_text)
                classification = sentiment_result["classification"]

                # Convert to score
                sentiment_score = 1 if classification == "pos" else -1

                analyzed_article = ArticleSentiment(
                    title=title or "No title",
                    description=description,
                    url=article.get("url"),
                    published_at=article.get("publishedAt"),
                    sentiment=classification,
                    sentiment_score=sentiment_score,
                )
                analyzed_articles.append(analyzed_article)

            except Exception as e:
                self.logger.error(f"Error analyzing article: {e}")
                continue

        return analyzed_articles


# Singleton instance
sentiment_analyzer = SentimentAnalyzer()
