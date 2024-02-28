from nltk.corpus import stopwords
from textblob import TextBlob
from textblob import Word
from textblob.sentiments import NaiveBayesAnalyzer
import requests
from settings import NEWSAPI_KEY


# Process data
def preprocess_text(text):
    blob = TextBlob(text)
    tokens = [word for word in blob.words if word not in stopwords.words('english')]
    text = ' '.join(tokens)
    return text


def get_sentiment(text):
    blob = TextBlob(text, analyzer=NaiveBayesAnalyzer())
    return blob.sentiment.classification


def get_stock_sentiment(stock):
    api_key = NEWSAPI_KEY
    url = f"https://newsapi.org/v2/everything?q={stock}&apiKey={api_key}"

    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for non-2xx status codes
        data = response.json()

        sentiments = []
        for article in data['articles']:
            title = article.get('title', '')
            description = article.get('description', '')

            # Ensure both title and description are strings before concatenation
            text = ' '.join(filter(None, [title, description]))
            text = preprocess_text(text)

            sentiment = get_sentiment(text) # returns pos or neg depending on if the article is possitive or negitive
            if sentiment == 'pos':
                sentiments.append(1)
            elif sentiment == 'neg':
                sentiments.append(-1)

        if len(sentiments) > 0:
            avg_sentiment = sum(sentiments) / len(sentiments)
            print(f'Average sentiment for {stock} is {avg_sentiment}')
        else:
            print(f'No articles found for {stock} in the specified date range.')

    except requests.exceptions.RequestException as e:
        print(f'An error occurred: {e}')



get_stock_sentiment('TSLA')
