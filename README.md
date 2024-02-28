# Stock Sentiment Analysis Tool

## Description
This Python tool automates the process of sentiment analysis for news articles related to a given stock symbol. It utilizes the Natural Language Toolkit (NLTK) to preprocess the text, removing stopwords, and then applies the TextBlob library's NaiveBayesAnalyzer to determine the sentiment of the text. The tool calculates the average sentiment score from multiple news articles to provide an overview of the current sentiment towards a stock.

## Installation
To run this tool, you will need Python and several dependencies. Install them using the following commands:

```bash
pip install nltk textblob requests
python -m textblob.download_corpora
```

Make sure you have an API key from NewsAPI, which you will insert into the `api_key` variable in the script.

## Usage

To analyze the sentiment for a particular stock, run the `get_stock_sentiment` function with the stock ticker as a string argument. For example:

```python
get_stock_sentiment('TSLA')  # Replace 'TSLA' with your target stock ticker
```

The function will output the average sentiment score for the specified stock based on the fetched news articles.

## API Key

You must replace the `api_key` variable's placeholder value with your actual API key from NewsAPI.

