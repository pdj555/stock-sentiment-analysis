from nltk.corpus import stopwords
from textblob import TextBlob
from textblob import Word
from textblob.sentiments import NaiveBayesAnalyzer
import requests
from settings.py import NEWSAPI_KEY


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
    url = f'https://newsapi.org/v2/everything?q={stock}&from=2023-08-01&to=2023-08-12&apiKey={api_key}'

    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for non-2xx status codes
        data = response.json()

        sentiments = []
        for article in data['articles']:
            text = article['title'] + ' ' + article['description']
            text = preprocess_text(text)

            sentiment = get_sentiment(text)
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


get_stock_sentiment('Meta')


# import concurrent.futures
# from nltk.corpus import stopwords
# from textblob import TextBlob
# from textblob.sentiments import NaiveBayesAnalyzer
# import requests
#
# stop_words_list = stopwords.words('english')
#
#
# # Process data
# def preprocess_text(text):
#     blob = TextBlob(text)
#     tokens = [word for word in blob.words if word not in stop_words_list]
#     text = ' '.join(tokens)
#     return text
#
#
# def get_sentiment(text):
#     blob = TextBlob(text, analyzer=NaiveBayesAnalyzer())
#     return blob.sentiment.classification
#
#
# def process_article(article):
#     text = article['title'] + ' ' + article['description']
#     text = preprocess_text(text)
#     return get_sentiment(text)
#
#
# def get_stock_sentiment(stock):
#     api_key = '96a4926ec75b4a8491cbd30b8a348c63'
#     url = f'https://newsapi.org/v2/everything?q={stock}&from=2023-08-01&to=2023-08-12&apiKey={api_key}'
#
#     try:
#         response = requests.get(url)
#         response.raise_for_status()  # Raise an exception for non-2xx status codes
#         data = response.json()
#
#         sentiments = []
#         articles = data['articles']
#
#         with concurrent.futures.ThreadPoolExecutor() as executor:
#             sentiment_results = list(executor.map(process_article, articles))
#
#         sentiments.extend([1 if sentiment == 'pos' else -1 for sentiment in sentiment_results])
#
#         if len(sentiments) > 0:
#             avg_sentiment = sum(sentiments) / len(sentiments)
#             print(f'Average sentiment for {stock} is {avg_sentiment}')
#         else:
#             print(f'No articles found for {stock} in the specified date range.')
#
#     except requests.exceptions.RequestException as e:
#         print(f'An error occurred: {e}')


# get_stock_sentiment('Apple')
