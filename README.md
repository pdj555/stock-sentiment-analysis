# Stock Sentiment Analysis API

[![CI/CD Pipeline](https://github.com/pdj555/stock-sentiment-analysis/workflows/CI/CD%20Pipeline/badge.svg)](https://github.com/pdj555/stock-sentiment-analysis/actions)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A production-ready REST API for analyzing sentiment of news articles related to stock symbols. Built with modern Python best practices, comprehensive testing, and containerization support.

## 🚀 Features

- **Modern REST API**: Built with FastAPI for high performance and automatic OpenAPI documentation
- **Sentiment Analysis**: Uses NLTK and TextBlob with NaiveBayesAnalyzer for accurate sentiment classification
- **News Integration**: Fetches real-time news articles from NewsAPI
- **Production Ready**:
  - Comprehensive error handling and logging (JSON structured logging)
  - Input validation with Pydantic
  - Health check endpoints
  - CORS support
  - Docker containerization
  - CI/CD pipeline with GitHub Actions
- **Well Tested**: Unit and integration tests with pytest
- **Type Safe**: Type hints throughout the codebase
- **Configurable**: Environment-based configuration management

## 📋 Requirements

- Python 3.12+
- NewsAPI API key (get one free at [newsapi.org](https://newsapi.org))
- Docker (optional, for containerized deployment)

## 🔧 Installation

### Local Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/pdj555/stock-sentiment-analysis.git
   cd stock-sentiment-analysis
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env and add your NewsAPI key
   ```

5. **Download NLTK data** (if not automatically done):
   ```bash
   python -c "import nltk; nltk.download('stopwords'); nltk.download('movie_reviews'); nltk.download('punkt')"
   ```

### Docker Installation

1. **Build and run with Docker Compose**:
   ```bash
   docker-compose up --build
   ```

2. **Or build manually**:
   ```bash
   docker build -t stock-sentiment-api .
   docker run -p 8000:8000 --env-file .env stock-sentiment-api
   ```

## 🎯 Usage

### Starting the API

**Local**:
```bash
# Development mode with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or using Python
python -m app.main
```

**Docker**:
```bash
docker-compose up
```

The API will be available at `http://localhost:8000`

### API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### Example API Calls

**Health Check**:
```bash
curl http://localhost:8000/health
```

**Analyze Stock Sentiment**:
```bash
curl -X POST "http://localhost:8000/sentiment/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "stock_symbol": "TSLA",
    "max_articles": 20
  }'
```

**Using Python**:
```python
import requests

response = requests.post(
    "http://localhost:8000/sentiment/analyze",
    json={"stock_symbol": "TSLA", "max_articles": 20}
)

data = response.json()
print(f"Average sentiment: {data['average_sentiment']}")
print(f"Total articles: {data['total_articles']}")
print(f"Positive: {data['positive_articles']}, Negative: {data['negative_articles']}")
```

## 📊 API Response Example

```json
{
  "stock_symbol": "TSLA",
  "average_sentiment": 0.65,
  "total_articles": 20,
  "positive_articles": 13,
  "negative_articles": 7,
  "articles": [
    {
      "title": "Tesla Reports Strong Q3 Earnings",
      "description": "Tesla exceeded expectations with record profits...",
      "url": "https://example.com/article",
      "published_at": "2023-10-20T10:00:00Z",
      "sentiment": "pos",
      "sentiment_score": 1
    }
  ]
}
```

## 🧪 Testing

**Run all tests**:
```bash
pytest
```

**Run with coverage**:
```bash
pytest --cov=app --cov-report=html
```

**Run specific test file**:
```bash
pytest tests/test_api.py -v
```

## 🔍 Code Quality

**Format code**:
```bash
black app/ tests/
```

**Lint code**:
```bash
flake8 app/ tests/
```

**Type checking**:
```bash
mypy app/
```

## 📁 Project Structure

```
stock-sentiment-analysis/
├── app/
│   ├── api/              # API routes
│   │   ├── health.py     # Health check endpoints
│   │   └── sentiment.py  # Sentiment analysis endpoints
│   ├── core/             # Core functionality
│   │   ├── config.py     # Configuration management
│   │   └── logging.py    # Logging setup
│   ├── models/           # Pydantic models
│   │   └── schemas.py    # Request/response schemas
│   ├── services/         # Business logic
│   │   ├── news.py       # NewsAPI client
│   │   └── sentiment.py  # Sentiment analyzer
│   └── main.py           # FastAPI application
├── tests/                # Test suite
│   ├── conftest.py       # Test fixtures
│   ├── test_api.py       # API tests
│   ├── test_news.py      # News service tests
│   └── test_sentiment.py # Sentiment service tests
├── .github/
│   └── workflows/
│       └── ci.yml        # CI/CD pipeline
├── Dockerfile            # Docker image definition
├── docker-compose.yml    # Docker Compose configuration
├── requirements.txt      # Production dependencies
├── requirements-dev.txt  # Development dependencies
├── .env.example          # Environment variables template
└── README.md             # This file
```

## ⚙️ Configuration

All configuration is done via environment variables. See `.env.example` for available options:

| Variable | Description | Default |
|----------|-------------|---------|
| `NEWSAPI_KEY` | Your NewsAPI key | (required) |
| `DEBUG` | Enable debug mode | `False` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `API_HOST` | API host | `0.0.0.0` |
| `API_PORT` | API port | `8000` |
| `CACHE_ENABLED` | Enable Redis caching | `False` |
| `RATE_LIMIT_ENABLED` | Enable rate limiting | `True` |

## 🚢 Deployment

### Docker Deployment

```bash
# Build image
docker build -t stock-sentiment-api:latest .

# Run container
docker run -d -p 8000:8000 --env-file .env stock-sentiment-api:latest
```

### Cloud Deployment

The application is ready for deployment to:
- **AWS**: ECS, Elastic Beanstalk, or Lambda
- **Google Cloud**: Cloud Run, App Engine
- **Azure**: Container Instances, App Service
- **Heroku**: Using Dockerfile

## 🔐 Security

- API key stored in environment variables (never in code)
- Input validation with Pydantic
- Rate limiting (configurable)
- CORS configuration
- Non-root Docker user
- Security headers (can be added via middleware)

## 📈 Monitoring

The API includes:
- Health check endpoint (`/health`)
- Structured JSON logging
- Ready for integration with monitoring tools (Prometheus, Datadog, etc.)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- [NewsAPI](https://newsapi.org/) for news data
- [FastAPI](https://fastapi.tiangolo.com/) for the excellent web framework
- [NLTK](https://www.nltk.org/) and [TextBlob](https://textblob.readthedocs.io/) for NLP capabilities

## 📧 Contact

For questions or support, please open an issue on GitHub.

---

**Note**: This is a production-ready application, but remember:
- Keep your NewsAPI key secure
- Monitor your API usage to stay within NewsAPI limits
- Consider implementing caching for production use
- Add authentication for production deployments
