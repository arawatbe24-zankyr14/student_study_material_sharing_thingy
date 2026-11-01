"""Entry point for Gunicorn in production:  gunicorn wsgi:app"""
from app import create_app

app = create_app()
