import os
import nltk
from nltk.corpus import stopwords
from textblob import TextBlob
from textblob import Word
from textblob.sentiments import NaiveBayesAnalyzer
import requests
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Download necessary NLTK data with error handling
try:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
    nltk.download('wordnet', quiet=True)
except Exception as e:
    print(f"NLTK download error: {e}")
    # Continue with default behavior if possible

# Process data with improved error handling
def preprocess_text(text):
    try:
        if not isinstance(text, str):
            return ""
            
        blob = TextBlob(text)
        tokens = [word for word in blob.words if word not in stopwords.words('english')]
        text = ' '.join(tokens)
        return text
    except Exception as e:
        print(f"Text preprocessing error: {e}")
        return text  # Return original text on error

def get_sentiment(text):
    try:
        if not text:
            return "neutral"
            
        blob = TextBlob(text, analyzer=NaiveBayesAnalyzer())
        return blob.sentiment.classification
    except Exception as e:
        print(f"Sentiment analysis error: {e}")
        return "neutral"  # Return neutral on error

def get_stock_sentiment(stock):
    # Get API key from environment variables
    api_key = os.environ.get("NEWSAPI_KEY")
    
    if not api_key:
        print("NewsAPI key not found in environment variables")
        return {"error": "NewsAPI key not found. Please set NEWSAPI_KEY environment variable."}
    
    url = f"https://newsapi.org/v2/everything?q={stock}&apiKey={api_key}"

    try:
        print(f"Fetching news for {stock}...")
        response = requests.get(url, timeout=10)  # Added timeout
        response.raise_for_status()  # Raise an exception for non-2xx status codes
        data = response.json()

        sentiments = []
        articles_processed = 0
        
        if "articles" not in data or not data["articles"]:
            print(f"No articles found for {stock}")
            return {"symbol": stock, "error": "No articles found"}
            
        print(f"Processing {len(data['articles'])} articles...")
        
        for article in data['articles']:
            title = article.get('title', '')
            description = article.get('description', '')

            # Ensure both title and description are strings before concatenation
            text = ' '.join(filter(None, [title, description]))
            
            if not text:
                continue
                
            text = preprocess_text(text)
            
            if not text:
                continue

            sentiment = get_sentiment(text)  # returns pos or neg depending on if the article is positive or negative
            articles_processed += 1
            
            if sentiment == 'pos':
                sentiments.append(1)
            elif sentiment == 'neg':
                sentiments.append(-1)
            else:
                sentiments.append(0)  # neutral

        if len(sentiments) > 0:
            avg_sentiment = sum(sentiments) / len(sentiments)
            print(f'Average sentiment for {stock} is {avg_sentiment:.2f} (from {articles_processed} articles)')
            return {
                "symbol": stock,
                "score": avg_sentiment,
                "articles": articles_processed
            }
        else:
            print(f'No valid articles found for {stock}.')
            return {"symbol": stock, "error": "No valid articles to analyze"}

    except requests.exceptions.RequestException as e:
        print(f'API request error: {e}')
        return {"symbol": stock, "error": str(e)}
    except Exception as e:
        print(f'An unexpected error occurred: {e}')
        return {"symbol": stock, "error": str(e)}

# Only run the analysis if this file is executed directly
if __name__ == "__main__":
    # Test with a few stocks
    stocks = ["TSLA", "AAPL", "MSFT"]
    results = {}
    
    for stock in stocks:
        result = get_stock_sentiment(stock)
        results[stock] = result
        
    # Print results in a readable format
    print("\nSummary of Results:")
    print("------------------")
    for stock, result in results.items():
        if "error" in result:
            print(f"{stock}: Error - {result['error']}")
        else:
            sentiment_text = "positive" if result.get("score", 0) > 0 else "negative" if result.get("score", 0) < 0 else "neutral"
            print(f"{stock}: {sentiment_text.upper()} ({result.get('score', 0):.2f}) from {result.get('articles', 0)} articles")
