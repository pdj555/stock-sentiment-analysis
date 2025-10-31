.PHONY: help install install-dev test lint format clean run docker-build docker-run docker-stop

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install production dependencies
	pip install -r requirements.txt
	python -c "import nltk; nltk.download('stopwords', quiet=True); nltk.download('movie_reviews', quiet=True); nltk.download('punkt', quiet=True)"

install-dev: ## Install development dependencies
	pip install -r requirements-dev.txt
	python -c "import nltk; nltk.download('stopwords', quiet=True); nltk.download('movie_reviews', quiet=True); nltk.download('punkt', quiet=True)"

test: ## Run tests with coverage
	pytest tests/ -v --cov=app --cov-report=term-missing --cov-report=html

test-quick: ## Run tests without coverage
	pytest tests/ -v

lint: ## Run linting
	flake8 app/ tests/ --max-line-length=100 --extend-ignore=E203,W503

format: ## Format code with black
	black app/ tests/

format-check: ## Check code formatting
	black --check app/ tests/

type-check: ## Run type checking
	mypy app/

quality: format lint type-check ## Run all code quality checks

clean: ## Clean temporary files and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true

run: ## Run the API server locally
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-prod: ## Run the API server in production mode
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

docker-build: ## Build Docker image
	docker build -t stock-sentiment-api:latest .

docker-run: ## Run Docker container
	docker run -d -p 8000:8000 --env-file .env --name stock-sentiment-api stock-sentiment-api:latest

docker-stop: ## Stop and remove Docker container
	docker stop stock-sentiment-api 2>/dev/null || true
	docker rm stock-sentiment-api 2>/dev/null || true

docker-compose-up: ## Start services with docker-compose
	docker-compose up --build

docker-compose-down: ## Stop services with docker-compose
	docker-compose down

logs: ## View API logs (when running in Docker)
	docker logs -f stock-sentiment-api

dev: install-dev ## Setup development environment
	@echo "Development environment ready!"
	@echo "Run 'make run' to start the server"

ci: format-check lint test ## Run CI checks locally
