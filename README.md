# AjoFinance

A community finance platform built with Plotly Dash and FastAPI.

## Prerequisites

- Python 3.12+
- PostgreSQL (for the FastAPI backend)

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/abelunbound/ajocredit.git
cd ajocredit
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install dependencies

For production:
```bash
pip install -r requirements.txt
```

For development (includes testing tools):
```bash
pip install -r requirements.txt -r requirements-dev.txt
```

## Running the Application

### Dash Web Application

The main web interface runs on port 8055:

```bash
python app_dash_web.py
```

Then visit http://localhost:8055 in your browser.

### FastAPI Backend (Optional)

The FastAPI service is a separate process for authentication and API endpoints. To run it:

```bash
uvicorn api:app --reload
```

This runs on http://localhost:8000 by default.

**Note:** The FastAPI service requires additional setup (database configuration, environment variables) which will be documented in future milestones.

## Development

### Running Tests

```bash
pytest
```

## Project Structure

- `app_dash_web.py` - Main Dash web application
- `api.py` - FastAPI backend service (authentication, API endpoints)
- `pages/` - Dash page components and layouts
- `requirements.txt` - Production dependencies (pinned versions)
- `requirements-dev.txt` - Development and testing dependencies
