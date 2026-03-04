web: gunicorn "src.app:app" --config gunicorn.conf.py
worker: python -m src.scheduler
release: python -c "from src.database import init_db; init_db()"
