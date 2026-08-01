.PHONY: help install lint format test run docker-build docker-run

help:
	@echo "Available commands:"
	@echo "  make install       Install dependencies"
	@echo "  make lint          Run ruff and black check"
	@echo "  make format        Format code with black and ruff"
	@echo "  make test          Run pytest suite"
	@echo "  make run           Run local dev server with uvicorn"
	@echo "  make docker-build  Build Docker image"
	@echo "  make docker-run    Run docker-compose environment"

install:
	pip install -r requirements.txt
	pip install -e .[dev]

lint:
	ruff check app tests
	black --check app tests

format:
	ruff check --fix app tests
	black app tests

test:
	PYTHONPATH=. pytest

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

docker-build:
	docker build -t saturdays-app:latest .

docker-run:
	docker-compose up --build
