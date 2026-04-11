FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY README.md app.py main.py pyproject.toml settings.py /app/
COPY stock_sentiment /app/stock_sentiment

EXPOSE 8080

CMD ["python", "-m", "stock_sentiment", "ui", "--host", "0.0.0.0", "--port", "8080"]
