FROM python:3.12-slim

# Install system dependencies needed for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default: run the API server via gunicorn.conf.py (reads $PORT automatically).
# Override CMD to "python -m src.scheduler" for the worker service.
CMD ["gunicorn", "src.app:app", "--config", "gunicorn.conf.py"]
