# InvestSense - Stock Sentiment Analysis Platform

InvestSense is a Flask-based web application that analyzes news sentiment for stocks and provides trading signals based on sentiment analysis.

## Features

- Real-time sentiment analysis of news articles for any stock symbol
- Historical sentiment tracking and visualization
- Correlation analysis between sentiment and stock price
- Trading signals based on sentiment analysis
- Responsive dashboard with interactive charts

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/stock-sentiment-analysis.git
cd stock-sentiment-analysis
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install the required packages:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root with your NewsAPI key:
```
NEWSAPI_KEY=your_newsapi_key_here
```

You can get a free API key from [NewsAPI.org](https://newsapi.org/register).

## Running the Application

Start the Flask development server:

```bash
python app.py
```

The application will be available at http://localhost:5000

## Usage

1. Enter a stock symbol (e.g., AAPL, MSFT, GOOGL) in the search box
2. View sentiment analysis, price correlation, and trading signals
3. Use the "Refresh Data" button to update the analysis with the latest news

## Troubleshooting

### Common Issues

1. **"NewsAPI key not found" error**
   - Make sure you've created a `.env` file with your NewsAPI key
   - Verify the key is valid and has not expired

2. **NLTK data download errors**
   - If you encounter NLTK download errors, manually download the required data:
   ```python
   import nltk
   nltk.download('punkt')
   nltk.download('stopwords')
   nltk.download('wordnet')
   ```

3. **Database errors**
   - If you encounter database errors, try deleting the `sentiment.db` file and restart the application
   - The database will be recreated automatically

4. **No data showing in dashboard**
   - Ensure your internet connection is working
   - Check if the NewsAPI daily request limit has been reached
   - Try a different stock symbol with more news coverage

### Logs

Check the console output for detailed error logs. The application has comprehensive error logging that should help identify any issues.

## Architecture

- **app.py**: Main Flask application with routes and database models
- **main.py**: Standalone script for testing sentiment analysis
- **templates/**: HTML templates for the web interface
- **settings.py**: Configuration settings and environment variable loading

## Dependencies

- Flask 2.0.1
- Flask-SQLAlchemy 2.5.1
- pandas 1.3.5
- plotly 5.5.0
- NLTK 3.6.7
- TextBlob 0.17.1
- yfinance 0.1.87
- aiohttp 3.7.4.post0
- APScheduler 3.9.1
- python-dotenv 0.19.2

## License

MIT
