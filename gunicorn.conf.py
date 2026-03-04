"""Gunicorn configuration file."""
import os
import sys

# Ensure the project root is on sys.path so `from src.xxx import` works
sys.path.insert(0, os.path.dirname(__file__))

# Server socket – Railway injects $PORT at runtime
bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"

# Worker processes
workers = int(os.getenv("WEB_CONCURRENCY", 2))
worker_class = "sync"
timeout = 120
keepalive = 5

# Logging
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()

# Process naming
proc_name = "arbitrage-api"


def on_starting(server):
    """Initialise DB tables before the first worker starts."""
    from src.database import init_db
    init_db()
