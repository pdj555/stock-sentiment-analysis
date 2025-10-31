"""API routes for sentiment analysis."""
from fastapi import APIRouter, HTTPException, status
from requests.exceptions import RequestException

from app.models import SentimentAnalysisRequest, SentimentAnalysisResponse
from app.services import news_client, sentiment_analyzer
from app.core import logger

router = APIRouter()


@router.post(
    "/analyze",
    response_model=SentimentAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze stock sentiment",
    description="Fetch news articles for a stock symbol and analyze sentiment",
)
async def analyze_stock_sentiment(request: SentimentAnalysisRequest) -> SentimentAnalysisResponse:
    """
    Analyze sentiment for a given stock symbol.

    Args:
        request: Sentiment analysis request with stock symbol

    Returns:
        Sentiment analysis response with average sentiment and article details

    Raises:
        HTTPException: If API request fails or no articles found
    """
    try:
        # Fetch articles
        logger.info(f"Analyzing sentiment for stock: {request.stock_symbol}")
        articles = news_client.get_articles_for_stock(
            stock_symbol=request.stock_symbol, max_articles=request.max_articles
        )

        if not articles:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No articles found for stock symbol: {request.stock_symbol}",
            )

        # Analyze sentiment
        analyzed_articles = sentiment_analyzer.analyze_articles(articles)

        if not analyzed_articles:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No valid articles to analyze for: {request.stock_symbol}",
            )

        # Calculate statistics
        total_articles = len(analyzed_articles)
        positive_articles = sum(1 for a in analyzed_articles if a.sentiment == "pos")
        negative_articles = sum(1 for a in analyzed_articles if a.sentiment == "neg")

        # Calculate average sentiment
        sentiment_scores = [a.sentiment_score for a in analyzed_articles]
        average_sentiment = sum(sentiment_scores) / len(sentiment_scores)

        logger.info(
            f"Analysis complete for {request.stock_symbol}: "
            f"avg={average_sentiment:.2f}, "
            f"articles={total_articles}"
        )

        return SentimentAnalysisResponse(
            stock_symbol=request.stock_symbol,
            average_sentiment=average_sentiment,
            total_articles=total_articles,
            positive_articles=positive_articles,
            negative_articles=negative_articles,
            articles=analyzed_articles,
        )

    except HTTPException:
        raise
    except RequestException as e:
        logger.error(f"News API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to fetch news articles: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Error analyzing sentiment: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )
