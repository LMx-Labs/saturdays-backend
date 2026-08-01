# Saturdays Monolithic Platform

This repository contains the backend implementation and canonical engineering architecture specification for Saturdays and DineGuru.

---

## Repository Structure

- `app/` — FastAPI application backend source code (Core Infrastructure, Config, Database, Middleware, Logging)
- `alembic/` & `alembic.ini` — PostgreSQL schema migrations
- `architecture/` — Canonical 15-year engineering architecture specification (116 files)
- `prompts/` — Governing prompt specifications and documentation rules
- `.github/workflows/` — CI/CD automation pipeline

---

## Local Setup & Quickstart

### Prerequisites
- Python 3.11+
- PostgreSQL 16+ (or Docker)

### Environment Configuration
Copy the sample environment file:
```bash
cp .env.example .env
```

### Installation
Install dependencies:
```bash
make install
# Or: pip install -r requirements.txt && pip install -e .[dev]
```

### Running Local Development Server
Start the FastAPI server:
```bash
make run
# Or: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
API Documentation available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Health Checks: `http://localhost:8000/health`, `/health/ready`, `/health/live`

### Docker Setup
Run the full stack via Docker Compose:
```bash
make docker-run
# Or: docker-compose up --build
```

### Testing & Code Quality
```bash
# Run Pytest suite
make test

# Code formatting & linting
make format
make lint
```