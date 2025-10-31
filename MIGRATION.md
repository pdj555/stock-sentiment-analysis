# Migration Guide: From Script to Production API

This guide helps you understand the changes made to transform the simple sentiment analysis script into a production-ready API.

## Overview of Changes

### Before (Original Script)
- Single `main.py` file with all logic
- Direct execution of sentiment analysis
- Limited error handling
- No tests
- No API interface
- Hardcoded configuration

### After (Production API)
- Modular architecture with separation of concerns
- REST API with FastAPI
- Comprehensive error handling and logging
- Full test suite with 83% coverage
- Docker containerization
- Environment-based configuration
- CI/CD pipeline

## Architecture Changes

### Old Structure
```
.
├── main.py           # All code in one file
├── settings.py       # Basic settings
└── README.md
```

### New Structure
```
.
├── app/
│   ├── api/              # API endpoints
│   │   ├── health.py     # Health checks
│   │   └── sentiment.py  # Sentiment analysis endpoints
│   ├── core/             # Core functionality
│   │   ├── config.py     # Configuration management
│   │   └── logging.py    # Logging setup
│   ├── models/           # Data models
│   │   └── schemas.py    # Pydantic schemas
│   ├── services/         # Business logic
│   │   ├── news.py       # NewsAPI client
│   │   └── sentiment.py  # Sentiment analyzer
│   └── main.py           # FastAPI application
├── tests/                # Test suite
├── Dockerfile            # Container definition
├── docker-compose.yml    # Docker orchestration
└── requirements.txt      # Dependencies
```

## Code Migration Examples

### Old Way: Direct Function Call
```python
# main.py (old)
from main import get_stock_sentiment

get_stock_sentiment('TSLA')
```

### New Way: REST API Call
```python
# Using the API
import requests

response = requests.post(
    "http://localhost:8000/sentiment/analyze",
    json={"stock_symbol": "TSLA", "max_articles": 20}
)
data = response.json()
print(f"Average sentiment: {data['average_sentiment']}")
```

### Old Way: Settings
```python
# settings.py (old)
from dotenv import load_dotenv
import os

load_dotenv()
NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY")
```

### New Way: Pydantic Settings
```python
# app/core/config.py (new)
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    newsapi_key: str
    debug: bool = False
    # ... more settings

    model_config = SettingsConfigDict(env_file=".env")
```

## Key Improvements

### 1. Error Handling
**Before**: Basic try-catch with print statements
```python
try:
    response = requests.get(url)
    data = response.json()
except requests.exceptions.RequestException as e:
    print(f'An error occurred: {e}')
```

**After**: Comprehensive error handling with proper HTTP status codes
```python
try:
    articles = news_client.get_articles_for_stock(...)
except RequestException as e:
    logger.error(f"News API error: {e}")
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"Failed to fetch news articles: {str(e)}"
    )
```

### 2. Logging
**Before**: Simple print statements
```python
print(f'Average sentiment for {stock} is {avg_sentiment}')
```

**After**: Structured JSON logging
```python
logger.info(
    f"Analysis complete for {request.stock_symbol}: "
    f"avg={average_sentiment:.2f}, articles={total_articles}"
)
```

### 3. Testing
**Before**: No tests

**After**: Comprehensive test suite
```python
def test_analyze_sentiment_success(mock_analyze, mock_get_articles, client):
    response = client.post(
        "/sentiment/analyze",
        json={"stock_symbol": "TSLA", "max_articles": 20}
    )
    assert response.status_code == 200
    # ... more assertions
```

### 4. API Response
**Before**: Print to console
```
Average sentiment for TSLA is 0.65
```

**After**: Structured JSON response
```json
{
  "stock_symbol": "TSLA",
  "average_sentiment": 0.65,
  "total_articles": 20,
  "positive_articles": 13,
  "negative_articles": 7,
  "articles": [...]
}
```

## Running the Application

### Old Way
```bash
python main.py  # Hardcoded to analyze TSLA
```

### New Way
```bash
# Start the API server
uvicorn app.main:app --reload

# Use the API
curl -X POST "http://localhost:8000/sentiment/analyze" \
  -H "Content-Type: application/json" \
  -d '{"stock_symbol": "TSLA", "max_articles": 20}'

# Or with Docker
docker-compose up
```

## Deployment

### Old Way
No deployment strategy - runs as a script

### New Way
Multiple deployment options:

1. **Docker**: `docker build -t stock-sentiment-api .`
2. **Cloud Services**: Ready for AWS ECS, Google Cloud Run, Azure
3. **Kubernetes**: Can create K8s manifests
4. **Serverless**: Can adapt for AWS Lambda/Azure Functions

## Testing & Quality

### Old Way
- No tests
- No linting
- No CI/CD

### New Way
```bash
# Run tests
pytest

# Code formatting
black app/ tests/

# Linting
flake8 app/ tests/

# CI/CD via GitHub Actions (automatic)
```

## Configuration

### Old Way: Direct .env file
```
NEWSAPI_KEY=your_key
```

### New Way: Comprehensive configuration
```bash
# .env file with all options
NEWSAPI_KEY=your_key
DEBUG=False
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=8000
CACHE_ENABLED=False
RATE_LIMIT_ENABLED=True
# ... more options
```

## Benefits of the New Architecture

1. **Scalability**: API can handle multiple concurrent requests
2. **Maintainability**: Modular code is easier to maintain and extend
3. **Testability**: Comprehensive test coverage ensures reliability
4. **Observability**: Structured logging and health checks
5. **Security**: Input validation, error handling, configurable rate limiting
6. **Documentation**: Automatic OpenAPI/Swagger documentation
7. **Deployment**: Container-ready with Docker support
8. **Development**: Modern tools (FastAPI, Pydantic, pytest)

## Next Steps

After deploying the new version, consider:

1. **Add Authentication**: Implement API keys or OAuth
2. **Enable Caching**: Use Redis to cache results
3. **Add Rate Limiting**: Protect against abuse
4. **Monitoring**: Integrate with Datadog, Prometheus, or similar
5. **Database**: Store historical sentiment data
6. **WebSocket**: Add real-time streaming updates
7. **Multiple Sources**: Integrate more news APIs
8. **Advanced NLP**: Use transformer models (BERT, GPT) for better accuracy

## Support

For questions or issues, please refer to:
- API Documentation: http://localhost:8000/docs
- README.md for setup instructions
- GitHub Issues for bug reports
