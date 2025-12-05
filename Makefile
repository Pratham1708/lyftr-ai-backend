.PHONY: help up down logs test clean

help:
	@echo "Lyftr AI Webhook Service - Makefile Commands"
	@echo ""
	@echo "  make up       - Start services with Docker Compose"
	@echo "  make down     - Stop services and remove volumes"
	@echo "  make logs     - View service logs"
	@echo "  make test     - Run tests"
	@echo "  make clean    - Clean temporary files"

up:
	docker compose up -d --build

down:
	docker compose down -v

logs:
	docker compose logs -f api

test:
	pytest tests/ -v --tb=short

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
