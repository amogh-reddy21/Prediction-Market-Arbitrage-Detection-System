"""Gunicorn configuration file."""
import os

# Server socket
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

# Lifecycle hooks – initialize the DB schema on first boot
def on_starting(server):
    from src.database import init_db
    init_db()
