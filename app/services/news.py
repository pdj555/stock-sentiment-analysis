"""NewsAPI client service."""
import logging
from typing import List, Dict, Any, Optional
import requests
from requests.exceptions import RequestException, HTTPError, Timeout

from app.core import settings


class NewsAPIClient:
    """Client for interacting with NewsAPI."""

    BASE_URL = "https://newsapi.org/v2"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize NewsAPI client.

        Args:
            api_key: NewsAPI key. If not provided, uses settings.
        """
        self.api_key = api_key or settings.newsapi_key
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()
        self.session.headers.update(
            {"X-Api-Key": self.api_key, "User-Agent": f"{settings.app_name}/{settings.app_version}"}
        )

    def get_everything(
        self, query: str, language: str = "en", sort_by: str = "publishedAt", page_size: int = 20
    ) -> Dict[str, Any]:
        """
        Fetch articles from NewsAPI everything endpoint.

        Args:
            query: Search query (e.g., stock symbol)
            language: Language code (default: 'en')
            sort_by: Sort order ('publishedAt', 'relevancy', 'popularity')
            page_size: Number of articles to retrieve (max 100)

        Returns:
            API response dictionary

        Raises:
            HTTPError: If API request fails
            Timeout: If request times out
            RequestException: For other request errors
        """
        url = f"{self.BASE_URL}/everything"

        params = {
            "q": query,
            "language": language,
            "sortBy": sort_by,
            "pageSize": min(page_size, 100),  # API max is 100
        }

        try:
            self.logger.info(f"Fetching news articles for query: {query}")
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "ok":
                error_msg = data.get("message", "Unknown error")
                self.logger.error(f"NewsAPI error: {error_msg}")
                raise HTTPError(f"NewsAPI error: {error_msg}")

            self.logger.info(f"Successfully fetched {len(data.get('articles', []))} articles")
            return data

        except Timeout as e:
            self.logger.error(f"NewsAPI request timeout: {e}")
            raise
        except HTTPError as e:
            self.logger.error(f"NewsAPI HTTP error: {e}")
            raise
        except RequestException as e:
            self.logger.error(f"NewsAPI request error: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error fetching news: {e}")
            raise

    def get_articles_for_stock(
        self, stock_symbol: str, max_articles: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get news articles for a specific stock symbol.

        Args:
            stock_symbol: Stock ticker symbol
            max_articles: Maximum number of articles to retrieve

        Returns:
            List of article dictionaries
        """
        try:
            data = self.get_everything(query=stock_symbol, page_size=max_articles)
            return data.get("articles", [])
        except Exception as e:
            self.logger.error(f"Error fetching articles for {stock_symbol}: {e}")
            raise

    def __del__(self):
        """Clean up session on deletion."""
        if hasattr(self, "session"):
            self.session.close()


# Singleton instance
news_client = NewsAPIClient()
