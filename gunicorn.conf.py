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
    import os
    db_url = os.getenv('DATABASE_URL', 'NOT SET')
    # Mask password for logging
    if '@' in db_url:
        safe_url = db_url.split('@')[1]
    else:
        safe_url = db_url
    print(f"[gunicorn] DATABASE_URL host: {safe_url}", flush=True)

    if db_url == 'NOT SET' or 'localhost' in db_url or '127.0.0.1' in db_url:
        print("[gunicorn] WARNING: DATABASE_URL is not set or points to localhost. Skipping init_db.", flush=True)
        return

    try:
        from src.database import init_db
        init_db()
    except Exception as e:
        print(f"[gunicorn] WARNING: init_db failed: {e}", flush=True)
