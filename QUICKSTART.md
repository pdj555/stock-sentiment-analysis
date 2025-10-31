# Quick Start Guide

Get the Stock Sentiment Analysis API up and running in 5 minutes!

## Prerequisites

- Python 3.12 or higher
- NewsAPI key (get free at https://newsapi.org)

## Installation (Local)

### 1. Clone and Navigate
```bash
cd stock-sentiment-analysis
```

### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment
```bash
cp .env.example .env
# Edit .env and add your NewsAPI key:
# NEWSAPI_KEY=your_actual_api_key_here
```

### 5. Start the Server
```bash
uvicorn app.main:app --reload
```

The API is now running at http://localhost:8000

## Quick Test

### 1. Check Health
```bash
curl http://localhost:8000/health
```

### 2. Analyze Stock Sentiment
```bash
curl -X POST http://localhost:8000/sentiment/analyze \
  -H "Content-Type: application/json" \
  -d '{"stock_symbol": "TSLA", "max_articles": 10}'
```

### 3. View API Documentation
Open your browser and visit:
- **Interactive Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc

## Docker Quick Start

Even faster with Docker!

### 1. Configure Environment
```bash
cp .env.example .env
# Edit .env and add your NewsAPI key
```

### 2. Start with Docker Compose
```bash
docker-compose up
```

That's it! API is running at http://localhost:8000

## Using Make

If you have `make` installed:

```bash
# Setup development environment
make dev

# Run the server
make run

# Run tests
make test

# See all available commands
make help
```

## Example API Usage

### Python
```python
import requests

response = requests.post(
    "http://localhost:8000/sentiment/analyze",
    json={"stock_symbol": "AAPL", "max_articles": 20}
)

data = response.json()
print(f"Stock: {data['stock_symbol']}")
print(f"Average Sentiment: {data['average_sentiment']:.2f}")
print(f"Total Articles: {data['total_articles']}")
print(f"Positive: {data['positive_articles']}, Negative: {data['negative_articles']}")
```

### JavaScript
```javascript
fetch('http://localhost:8000/sentiment/analyze', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ stock_symbol: 'GOOGL', max_articles: 15 })
})
.then(res => res.json())
.then(data => console.log(data));
```

### cURL
```bash
curl -X POST "http://localhost:8000/sentiment/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "stock_symbol": "MSFT",
    "max_articles": 25
  }'
```

## Common Issues

### "ModuleNotFoundError"
Make sure you've activated your virtual environment and installed dependencies:
```bash
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### "NEWSAPI_KEY not found"
Make sure you've created a `.env` file with your API key:
```bash
cp .env.example .env
# Edit .env and add: NEWSAPI_KEY=your_key_here
```

### NLTK Data Missing
The app downloads required NLTK data automatically on startup, but you can manually download it:
```bash
python -c "import nltk; nltk.download('stopwords'); nltk.download('movie_reviews'); nltk.download('punkt')"
```

### Port 8000 Already in Use
Change the port in `.env`:
```
API_PORT=8001
```

Or specify when running:
```bash
uvicorn app.main:app --port 8001
```

## Next Steps

- 📖 Read the full [README.md](README.md) for detailed documentation
- 🔄 Check [MIGRATION.md](MIGRATION.md) to understand the architecture changes
- 🐳 See [Docker documentation](Dockerfile) for deployment options
- 🧪 Run tests with `pytest tests/` or `make test`
- 🎨 Explore the API at http://localhost:8000/docs

## Getting Help

- API Documentation: http://localhost:8000/docs (when server is running)
- GitHub Issues: Report bugs or request features
- README.md: Comprehensive documentation

Happy analyzing! 📈
