import os
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_caching import Cache
from datetime import datetime, timedelta
import pandas as pd
import plotly
import plotly.express as px
import plotly.graph_objects as go
import json
import asyncio
import aiohttp
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer
import nltk
from textblob import TextBlob
import yfinance as yf
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
import time
import atexit

# Download necessary NLTK data with error handling
try:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
    nltk.download('wordnet', quiet=True)
except Exception as e:
    print(f"NLTK download error: {e}")
    # Continue with default behavior if possible

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sentiment.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['CACHE_TYPE'] = 'SimpleCache'
app.config['CACHE_DEFAULT_TIMEOUT'] = 3600  # 1 hour default cache timeout

# Initialize extensions
db = SQLAlchemy(app)
cache = Cache(app)

# Database models
class StockSentiment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    sentiment_score = db.Column(db.Float, nullable=False)
    sentiment_magnitude = db.Column(db.Float, nullable=False)
    article_count = db.Column(db.Integer, nullable=False)
    
class StockPrice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    open_price = db.Column(db.Float, nullable=False)
    close_price = db.Column(db.Float, nullable=False)
    volume = db.Column(db.Integer, nullable=False)

# Create tables with proper error handling
try:
    with app.app_context():
        db.create_all()
except Exception as e:
    print(f"Database initialization error: {e}")
    # For Flask < 2.0 compatibility
    try:
        ctx = app.app_context()
        ctx.push()
        db.create_all()
        ctx.pop()
        print("Database tables created using compatibility mode")
    except Exception as e2:
        print(f"Failed to create database tables: {e2}")

# Enhanced text preprocessing
lemmatizer = WordNetLemmatizer()
try:
    stop_words = set(stopwords.words('english'))
except Exception as e:
    print(f"Error loading stopwords: {e}")
    stop_words = set()  # Fallback to empty set

def preprocess_text(text):
    if not isinstance(text, str):
        return ""
    
    try:
        # Tokenize and convert to lowercase
        tokens = word_tokenize(text.lower())
        
        # Remove stopwords and lemmatize
        tokens = [lemmatizer.lemmatize(word) for word in tokens if word.isalpha() and word not in stop_words]
        
        return " ".join(tokens)
    except Exception as e:
        print(f"Text preprocessing error: {e}")
        return text  # Return original text on error

# Advanced sentiment analysis
def analyze_sentiment(text):
    if not text:
        return {"score": 0, "magnitude": 0}
    
    try:
        blob = TextBlob(text)
        
        # TextBlob polarity ranges from -1 (negative) to 1 (positive)
        score = blob.sentiment.polarity
        
        # Use subjectivity as magnitude (0 = objective, 1 = subjective)
        magnitude = blob.sentiment.subjectivity
        
        return {"score": score, "magnitude": magnitude}
    except Exception as e:
        print(f"Sentiment analysis error: {e}")
        return {"score": 0, "magnitude": 0}  # Return neutral on error

# Enhanced sentiment analysis with financial context
def analyze_sentiment_enhanced(text, symbol):
    # Basic TextBlob analysis as fallback
    basic_sentiment = analyze_sentiment(text)
    
    try:
        # Symbol-specific context analysis
        industry_keywords = get_industry_keywords(symbol)
        financial_terms = {"revenue", "profit", "growth", "earnings", "guidance", "forecast", 
                          "dividend", "margin", "eps", "outlook", "target", "upgrade", "downgrade"}
        
        # Weight sentiment based on financial term proximity
        sentiment_score = basic_sentiment["score"]
        
        # Boost sentiment impact when near financial terms
        for term in financial_terms:
            if term in text.lower():
                # Financial terms carry more weight in analysis
                sentiment_score *= 1.2
                
        # Consider industry-specific sentiment modifiers
        for keyword in industry_keywords:
            if keyword in text.lower():
                sentiment_score *= 1.1
                
        return {
            "score": max(min(sentiment_score, 1.0), -1.0),  # Clamp between -1 and 1
            "magnitude": basic_sentiment["magnitude"],
            "context": "financial" if any(term in text.lower() for term in financial_terms) else "general"
        }
    except Exception as e:
        print(f"Enhanced sentiment analysis error: {e}")
        return basic_sentiment  # Fall back to basic sentiment on error

# Get industry-specific keywords for a stock symbol
def get_industry_keywords(symbol):
    # Default keywords for all industries
    default_keywords = {"market", "investor", "stock", "share", "trading"}
    
    # Industry-specific dictionaries
    tech_keywords = {"innovation", "product", "software", "hardware", "cloud", "ai", "data", "platform"}
    retail_keywords = {"consumer", "sales", "store", "e-commerce", "customer", "shopping"}
    finance_keywords = {"bank", "interest", "loan", "deposit", "credit", "mortgage", "asset"}
    healthcare_keywords = {"patient", "drug", "clinical", "trial", "fda", "approval", "treatment"}
    energy_keywords = {"oil", "gas", "renewable", "production", "reserve", "drilling"}
    
    # Map symbols to industries (simplified example)
    tech_symbols = {"AAPL", "MSFT", "GOOGL", "META", "AMZN", "NVDA", "INTC", "AMD", "CRM", "ADBE"}
    retail_symbols = {"WMT", "TGT", "COST", "HD", "LOW", "AMZN", "JWN", "M", "KSS"}
    finance_symbols = {"JPM", "BAC", "WFC", "C", "GS", "MS", "AXP", "V", "MA", "BLK"}
    healthcare_symbols = {"JNJ", "PFE", "MRK", "ABBV", "BMY", "UNH", "CVS", "GILD", "AMGN", "BIIB"}
    energy_symbols = {"XOM", "CVX", "COP", "EOG", "SLB", "OXY", "PSX", "VLO", "MPC", "KMI"}
    
    # Return appropriate keywords based on symbol
    if symbol in tech_symbols:
        return default_keywords.union(tech_keywords)
    elif symbol in retail_symbols:
        return default_keywords.union(retail_keywords)
    elif symbol in finance_symbols:
        return default_keywords.union(finance_keywords)
    elif symbol in healthcare_symbols:
        return default_keywords.union(healthcare_keywords)
    elif symbol in energy_symbols:
        return default_keywords.union(energy_keywords)
    else:
        return default_keywords

# Async news fetching with improved error handling
async def fetch_news(session, symbol, days_back=7):
    newsapi_key = os.environ.get("NEWSAPI_KEY")
    if not newsapi_key:
        return {"error": "NewsAPI key not found. Please set NEWSAPI_KEY environment variable."}
    
    from_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
    to_date = datetime.now().strftime('%Y-%m-%d')
    
    url = f"https://newsapi.org/v2/everything?q={symbol}&from={from_date}&to={to_date}&language=en&sortBy=publishedAt&apiKey={newsapi_key}"
    
    # Implement exponential backoff for rate limiting
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            async with session.get(url, timeout=10) as response:
                if response.status == 429:  # Too Many Requests
                    print(f"Rate limit hit, attempt {attempt+1}/{max_retries}, waiting {retry_delay}s")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                
                if response.status != 200:
                    error_text = await response.text()
                    return {"error": f"NewsAPI returned status {response.status}: {error_text}"}
                
                data = await response.json()
                return data
        except asyncio.TimeoutError:
            print(f"Request timeout, attempt {attempt+1}/{max_retries}")
            await asyncio.sleep(retry_delay)
            retry_delay *= 2
        except Exception as e:
            if "rate limit" in str(e).lower():
                print(f"Rate limit error, attempt {attempt+1}/{max_retries}")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
            else:
                return {"error": str(e)}
    
    return {"error": "Maximum retries reached"}

# Process news articles and analyze sentiment with better error handling
async def process_stock_sentiment(symbol, days_back=7):
    if not symbol or not isinstance(symbol, str):
        return {"symbol": str(symbol), "error": "Invalid symbol format"}
        
    try:
        async with aiohttp.ClientSession() as session:
            news_data = await fetch_news(session, symbol, days_back)
            
            if "error" in news_data:
                print(f"Error fetching news for {symbol}: {news_data['error']}")
                return {"symbol": symbol, "error": news_data['error']}
            
            if "articles" not in news_data or not news_data["articles"]:
                print(f"No articles found for {symbol}")
                return {"symbol": symbol, "error": "No articles found"}
            
            sentiments = []
            
            for article in news_data["articles"]:
                title = article.get("title", "")
                description = article.get("description", "")
                content = article.get("content", "")
                
                # Combine text elements
                text = " ".join(filter(None, [title, description, content]))
                
                # Skip empty articles
                if not text.strip():
                    continue
                    
                # Preprocess text
                processed_text = preprocess_text(text)
                
                # Skip if preprocessing failed
                if not processed_text:
                    continue
                
                # Analyze sentiment
                sentiment = analyze_sentiment_enhanced(processed_text, symbol)
                sentiments.append(sentiment)
            
            if not sentiments:
                return {"symbol": symbol, "error": "No valid articles to analyze"}
            
            # Calculate average sentiment
            avg_score = sum(s["score"] for s in sentiments) / len(sentiments)
            avg_magnitude = sum(s["magnitude"] for s in sentiments) / len(sentiments)
            
            # Store in database
            try:
                with app.app_context():
                    new_sentiment = StockSentiment(
                        symbol=symbol,
                        date=datetime.now(),
                        sentiment_score=avg_score,
                        sentiment_magnitude=avg_magnitude,
                        article_count=len(sentiments)
                    )
                    db.session.add(new_sentiment)
                    db.session.commit()
            except Exception as db_error:
                print(f"Database error storing sentiment for {symbol}: {db_error}")
                # Continue without failing the whole request
            
            return {"symbol": symbol, "score": avg_score, "magnitude": avg_magnitude, "articles": len(sentiments)}
    except Exception as e:
        print(f"Error processing sentiment for {symbol}: {e}")
        return {"symbol": symbol, "error": str(e)}

# Get financial metrics for a stock
@cache.memoize(timeout=3600)  # Cache for 1 hour
def get_financial_metrics(symbol):
    try:
        stock = yf.Ticker(symbol)
        
        # Get key statistics with timeout
        info = {}
        try:
            # Sometimes yfinance info call can hang
            info = stock.info
        except Exception as ticker_error:
            print(f"Error getting ticker info for {symbol}: {ticker_error}")
            return {}
        
        # Check if we got valid data
        if not info or not isinstance(info, dict) or len(info) < 5:
            print(f"Insufficient data returned for {symbol}")
            return {}
        
        return {
            "pe_ratio": info.get("trailingPE", None),
            "market_cap": info.get("marketCap", None),
            "dividend_yield": info.get("dividendYield", None) * 100 if info.get("dividendYield") else None,
            "52wk_high": info.get("fiftyTwoWeekHigh", None),
            "52wk_low": info.get("fiftyTwoWeekLow", None),
            "avg_volume": info.get("averageVolume", None),
            "beta": info.get("beta", None),
            "eps": info.get("trailingEps", None)
        }
    except Exception as e:
        print(f"Error fetching financial metrics for {symbol}: {e}")
        return {}

# Fetch historical stock data with improved error handling
def fetch_stock_prices(symbol, days_back=30):
    try:
        stock = yf.Ticker(symbol)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        history = stock.history(start=start_date, end=end_date)
        
        if history.empty:
            print(f"No historical data found for {symbol}")
            return None
        
        # Store in database
        try:
            with app.app_context():
                for date, row in history.iterrows():
                    # Check if we already have this date
                    existing = StockPrice.query.filter_by(symbol=symbol, date=date).first()
                    if not existing:
                        new_price = StockPrice(
                            symbol=symbol,
                            date=date,
                            open_price=row["Open"],
                            close_price=row["Close"],
                            volume=row["Volume"]
                        )
                        db.session.add(new_price)
                db.session.commit()
        except Exception as db_error:
            print(f"Database error storing price data for {symbol}: {db_error}")
            # Continue without storing in DB
        
        return history
    except Exception as e:
        print(f"Error fetching stock data for {symbol}: {e}")
        return None

# Enhanced trading signals with more sophisticated rules
def generate_enhanced_signals(symbol, days_back=30):
    try:
        with app.app_context():
            # Get data
            sentiment_data = StockSentiment.query.filter_by(symbol=symbol).order_by(StockSentiment.date.desc()).limit(days_back).all()
            price_data = StockPrice.query.filter_by(symbol=symbol).order_by(StockPrice.date.desc()).limit(days_back).all()
            
            if not sentiment_data or len(sentiment_data) < 2:
                return {"error": "Insufficient sentiment data"}
                
            if not price_data or len(price_data) < 2:
                return {"error": "Insufficient price data"}
            
            # Recent sentiment values
            current_sentiment = sentiment_data[0]
            previous_sentiment = sentiment_data[1]
            
            # Recent price values
            current_price = price_data[0].close_price
            previous_price = price_data[1].close_price
            
            # Calculate momentum and trends
            sentiment_change = current_sentiment.sentiment_score - previous_sentiment.sentiment_score
            price_change_pct = (current_price - previous_price) / previous_price * 100
            
            signals = []
            
            # Strong buy signals
            if current_sentiment.sentiment_score > 0.4 and sentiment_change > 0.2:
                signals.append({
                    "type": "BUY",
                    "strength": "STRONG",
                    "reason": f"Strongly positive sentiment ({current_sentiment.sentiment_score:.2f}) with improving trend (+{sentiment_change:.2f})"
                })
            # Momentum buy signals
            elif current_sentiment.sentiment_score > 0.2 and sentiment_change > 0:
                signals.append({
                    "type": "BUY",
                    "strength": "MODERATE",
                    "reason": f"Positive sentiment ({current_sentiment.sentiment_score:.2f}) with upward momentum"
                })
            # Contrarian buy signals (negative sentiment but improving)
            elif current_sentiment.sentiment_score < 0 and sentiment_change > 0.3:
                signals.append({
                    "type": "BUY",
                    "strength": "SPECULATIVE",
                    "reason": "Negative but rapidly improving sentiment, possible contrarian opportunity"
                })
            # Strong sell signals
            elif current_sentiment.sentiment_score < -0.4 and sentiment_change < -0.2:
                signals.append({
                    "type": "SELL",
                    "strength": "STRONG",
                    "reason": f"Strongly negative sentiment ({current_sentiment.sentiment_score:.2f}) with deteriorating trend ({sentiment_change:.2f})"
                })
            # Momentum sell signals
            elif current_sentiment.sentiment_score < -0.2 and sentiment_change < 0:
                signals.append({
                    "type": "SELL",
                    "strength": "MODERATE",
                    "reason": f"Negative sentiment ({current_sentiment.sentiment_score:.2f}) with downward momentum"
                })
            # Divergence signals (sentiment and price moving opposite directions)
            elif (sentiment_change > 0.2 and price_change_pct < -2) or (sentiment_change < -0.2 and price_change_pct > 2):
                signals.append({
                    "type": "RESEARCH",
                    "strength": "URGENT",
                    "reason": "Significant divergence between sentiment and price movement, further research recommended"
                })
            else:
                signals.append({
                    "type": "HOLD",
                    "strength": "NEUTRAL",
                    "reason": "No strong sentiment signals detected"
                })
                
            # Add additional context
            signals[0]["metrics"] = {
                "current_sentiment": current_sentiment.sentiment_score,
                "sentiment_change": sentiment_change,
                "price_change_pct": price_change_pct,
                "confidence": current_sentiment.sentiment_magnitude
            }
            
            # Add correlation analysis if available
            correlation_data = analyze_lagged_correlation(symbol)
            if correlation_data:
                signals[0]["correlation"] = correlation_data
            
            return signals
    except Exception as e:
        print(f"Error generating enhanced signals for {symbol}: {e}")
        return {"error": f"Error generating signals: {str(e)}"}

# Generate trading signals with error handling (legacy version kept for compatibility)
def generate_signals(symbol, days_back=30):
    try:
        # Use the enhanced signals function
        return generate_enhanced_signals(symbol, days_back)
    except Exception as e:
        print(f"Error generating signals for {symbol}: {e}")
        return {"error": f"Error generating signals: {str(e)}"}

# Background job to update sentiment data with improved error handling
def update_all_sentiments():
    print("Starting scheduled sentiment update...")
    # List of stocks to track - can be expanded
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA"]
    
    for symbol in symbols:
        try:
            print(f"Updating data for {symbol}...")
            # Update stock prices
            fetch_stock_prices(symbol)
            
            # Update sentiment (use asyncio in a sync context)
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(process_stock_sentiment(symbol))
                loop.close()
            except Exception as async_error:
                print(f"Asyncio error for {symbol}: {async_error}")
            
            time.sleep(1)  # Avoid hitting API rate limits
        except Exception as e:
            print(f"Error updating {symbol}: {e}")
    
    print("Scheduled sentiment update completed")

# Set up the scheduler with proper shutdown handling
scheduler = BackgroundScheduler()
scheduler.add_job(func=update_all_sentiments, trigger="interval", hours=12)
scheduler.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())

# Create dashboard visualizations with error handling
def create_sentiment_chart(symbol, days_back=30):
    try:
        with app.app_context():
            sentiment_data = StockSentiment.query.filter_by(symbol=symbol).order_by(StockSentiment.date.desc()).limit(days_back).all()
            
            if not sentiment_data:
                return None
            
            df = pd.DataFrame([
                {"date": s.date, "score": s.sentiment_score, "magnitude": s.sentiment_magnitude, "articles": s.article_count} 
                for s in sentiment_data
            ])
            
            df = df.sort_values("date")
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df["date"], 
                y=df["score"], 
                mode="lines+markers", 
                name="Sentiment Score",
                marker=dict(size=df["magnitude"]*10)
            ))
            
            fig.update_layout(
                title=f"Sentiment Analysis for {symbol}",
                xaxis_title="Date",
                yaxis_title="Sentiment Score (-1 to 1)",
                template="plotly_white"
            )
            
            return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    except Exception as e:
        print(f"Error creating sentiment chart for {symbol}: {e}")
        return None

# Price-Sentiment Correlation Analysis
def analyze_lagged_correlation(symbol, lag_days=1, history_days=60):
    try:
        with app.app_context():
            # Get sentiment and price data
            sentiment_data = StockSentiment.query.filter_by(symbol=symbol).order_by(StockSentiment.date.desc()).limit(history_days).all()
            price_data = StockPrice.query.filter_by(symbol=symbol).order_by(StockPrice.date.desc()).limit(history_days).all()
            
            if not sentiment_data or not price_data:
                return None
            
            # Create dataframes
            sentiment_df = pd.DataFrame([
                {"date": s.date, "score": s.sentiment_score} 
                for s in sentiment_data
            ]).sort_values("date")
            
            price_df = pd.DataFrame([
                {"date": p.date, "close": p.close_price} 
                for p in price_data
            ]).sort_values("date")
            
            # Convert dates
            sentiment_df["date"] = pd.to_datetime(sentiment_df["date"]).dt.date
            price_df["date"] = pd.to_datetime(price_df["date"]).dt.date
            
            # Create lagged sentiment (predicting future price movements)
            sentiment_df["date_lagged"] = sentiment_df["date"].apply(lambda x: x + timedelta(days=lag_days))
            
            # Merge based on lagged dates
            merged_df = pd.merge(
                sentiment_df[["date_lagged", "score"]], 
                price_df[["date", "close"]], 
                left_on="date_lagged", 
                right_on="date", 
                how="inner"
            )
            
            if len(merged_df) < 5:  # Need minimum data points
                return None
                
            # Calculate correlation
            correlation = merged_df["score"].corr(merged_df["close"])
            
            return {
                "correlation": correlation,
                "lag_days": lag_days,
                "data_points": len(merged_df),
                "predictive_power": abs(correlation) * 100  # As a percentage
            }
    except Exception as e:
        print(f"Error analyzing lagged correlation for {symbol}: {e}")
        return None

def create_correlation_chart(symbol, days_back=30):
    try:
        with app.app_context():
            sentiment_data = StockSentiment.query.filter_by(symbol=symbol).order_by(StockSentiment.date.desc()).limit(days_back).all()
            price_data = StockPrice.query.filter_by(symbol=symbol).order_by(StockPrice.date.desc()).limit(days_back).all()
            
            if not sentiment_data or not price_data:
                return None
            
            sentiment_df = pd.DataFrame([
                {"date": s.date, "score": s.sentiment_score} 
                for s in sentiment_data
            ])
            
            price_df = pd.DataFrame([
                {"date": p.date, "close": p.close_price} 
                for p in price_data
            ])
            
            # Convert to common date format for merging
            sentiment_df["date"] = pd.to_datetime(sentiment_df["date"]).dt.date
            price_df["date"] = pd.to_datetime(price_df["date"]).dt.date
            
            # Merge datasets
            merged_df = pd.merge(sentiment_df, price_df, on="date", how="inner")
            
            if merged_df.empty:
                return None
            
            # Create dual-axis chart
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=merged_df["date"],
                y=merged_df["score"],
                name="Sentiment Score",
                mode="lines+markers",
                line=dict(color="blue")
            ))
            
            fig.add_trace(go.Scatter(
                x=merged_df["date"],
                y=merged_df["close"],
                name="Stock Price",
                mode="lines",
                line=dict(color="green"),
                yaxis="y2"
            ))
            
            fig.update_layout(
                title=f"Sentiment vs. Price for {symbol}",
                xaxis=dict(title="Date"),
                yaxis=dict(
                    title="Sentiment Score",
                    titlefont=dict(color="blue"),
                    tickfont=dict(color="blue")
                ),
                yaxis2=dict(
                    title="Stock Price ($)",
                    titlefont=dict(color="green"),
                    tickfont=dict(color="green"),
                    overlaying="y",
                    side="right"
                ),
                template="plotly_white"
            )
            
            return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    except Exception as e:
        print(f"Error creating correlation chart for {symbol}: {e}")
        return None

# Flask routes with improved error handling
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/portfolio')
def portfolio_view():
    try:
        # Get stocks from request or use defaults
        stocks_param = request.args.get('stocks', 'AAPL,MSFT,GOOGL,AMZN')
        stocks = [s.strip().upper() for s in stocks_param.split(',') if s.strip()]
        
        if not stocks:
            stocks = ['AAPL', 'MSFT', 'GOOGL', 'AMZN']  # Default if none provided
        
        portfolio_data = {}
        sentiment_trend = []
        
        for symbol in stocks:
            try:
                with app.app_context():
                    # Get latest sentiment
                    latest = StockSentiment.query.filter_by(symbol=symbol).order_by(StockSentiment.date.desc()).first()
                    
                    if latest:
                        portfolio_data[symbol] = {
                            "sentiment": latest.sentiment_score,
                            "magnitude": latest.sentiment_magnitude,
                            "date": latest.date
                        }
                        
                        # Get historical data for trends (last 7 days)
                        historical = StockSentiment.query.filter_by(symbol=symbol).order_by(StockSentiment.date.desc()).limit(7).all()
                        
                        if historical and len(historical) > 1:
                            for entry in reversed(historical):
                                sentiment_trend.append({
                                    "symbol": symbol,
                                    "date": entry.date.strftime('%Y-%m-%d'),
                                    "score": entry.sentiment_score
                                })
            except Exception as e:
                print(f"Error processing portfolio data for {symbol}: {e}")
        
        # Calculate portfolio sentiment score (weighted by magnitude)
        portfolio_sentiment = 0
        if portfolio_data:
            total_magnitude = sum(data["magnitude"] for data in portfolio_data.values())
            if total_magnitude > 0:
                portfolio_sentiment = sum(data["sentiment"] * data["magnitude"] for data in portfolio_data.values()) / total_magnitude
        
        return render_template(
            'portfolio.html',
            stocks=stocks,
            portfolio_data=portfolio_data,
            portfolio_sentiment=portfolio_sentiment,
            sentiment_trend=sentiment_trend
        )
    except Exception as e:
        print(f"Portfolio view error: {e}")
        return render_template('portfolio.html', stocks=[], portfolio_data={}, 
                              portfolio_sentiment=0, sentiment_trend=[], 
                              error=f"Error loading portfolio data: {str(e)}")

@app.route('/dashboard/<symbol>')
def dashboard(symbol):
    try:
        # Validate symbol
        if not symbol.isalpha():
            return render_template('index.html', error="Invalid stock symbol format")
            
        symbol = symbol.upper()
        
        # Check if symbol exists in our database
        with app.app_context():
            sentiment_data = StockSentiment.query.filter_by(symbol=symbol).first()
            if not sentiment_data:
                # If no data exists, trigger an update
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    result = loop.run_until_complete(process_stock_sentiment(symbol))
                    loop.close()
                    
                    # Check if we got an error
                    if result and "error" in result:
                        return render_template('dashboard.html', symbol=symbol, error=result["error"])
                    
                    fetch_stock_prices(symbol)
                except Exception as e:
                    print(f"Error initializing data for {symbol}: {e}")
                    return render_template('dashboard.html', symbol=symbol, error=f"Error fetching data: {str(e)}")
        
        sentiment_chart = create_sentiment_chart(symbol)
        correlation_chart = create_correlation_chart(symbol)
        signals = generate_enhanced_signals(symbol)
        
        return render_template(
            'dashboard.html',
            symbol=symbol,
            sentiment_chart=sentiment_chart,
            correlation_chart=correlation_chart,
            signals=signals
        )
    except Exception as e:
        print(f"Dashboard error for {symbol}: {e}")
        return render_template('dashboard.html', symbol=symbol, error=f"Error loading dashboard: {str(e)}")

@app.route('/api/symbols')
@cache.cached(timeout=3600)  # Cache for 1 hour
def get_symbols():
    try:
        with app.app_context():
            symbols = db.session.query(StockSentiment.symbol).distinct().all()
            return jsonify([s[0] for s in symbols])
    except Exception as e:
        print(f"Error fetching symbols: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/sentiment/<symbol>')
@cache.cached(timeout=1800)  # Cache for 30 minutes
def get_sentiment(symbol):
    try:
        days = request.args.get('days', default=30, type=int)
        
        with app.app_context():
            sentiment_data = StockSentiment.query.filter_by(symbol=symbol).order_by(StockSentiment.date.desc()).limit(days).all()
            result = [
                {
                    "date": s.date.isoformat(),
                    "score": s.sentiment_score,
                    "magnitude": s.sentiment_magnitude,
                    "articles": s.article_count
                }
                for s in sentiment_data
            ]
            return jsonify(result)
    except Exception as e:
        print(f"Error fetching sentiment for {symbol}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/signals/<symbol>')
@cache.cached(timeout=1800)  # Cache for 30 minutes
def get_signals(symbol):
    try:
        signals = generate_signals(symbol)
        return jsonify(signals)
    except Exception as e:
        print(f"Error fetching signals for {symbol}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/correlation/<symbol>')
@cache.cached(timeout=3600)  # Cache for 1 hour
def get_correlation(symbol):
    try:
        correlation = analyze_lagged_correlation(symbol)
        if correlation:
            return jsonify(correlation)
        else:
            return jsonify({"error": "Insufficient data for correlation analysis"}), 404
    except Exception as e:
        print(f"Error fetching correlation for {symbol}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/metrics/<symbol>')
@cache.cached(timeout=3600)  # Cache for 1 hour
def get_metrics(symbol):
    try:
        metrics = get_financial_metrics(symbol)
        if metrics:
            return jsonify(metrics)
        else:
            return jsonify({"error": "Unable to fetch financial metrics"}), 404
    except Exception as e:
        print(f"Error fetching financial metrics for {symbol}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/analyze', methods=['POST'])
def analyze():
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "No JSON data provided"}), 400
        
        symbol = data.get('symbol')
        
        if not symbol:
            return jsonify({"status": "error", "message": "Symbol is required"}), 400
        
        # Validate symbol format (basic validation)
        if not isinstance(symbol, str) or not symbol.isalpha() or len(symbol) > 10:
            return jsonify({"status": "error", "message": "Invalid symbol format"}), 400
        
        symbol = symbol.upper()  # Standardize to uppercase
        
        # Run analysis in background to avoid blocking
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(process_stock_sentiment(symbol))
            loop.close()
            
            if result and "error" in result:
                return jsonify({"status": "error", "message": result["error"]}), 500
            
            fetch_stock_prices(symbol)
            
            return jsonify({"status": "success", "data": result})
        except Exception as e:
            print(f"Analysis error for {symbol}: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
    except Exception as e:
        print(f"API error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
