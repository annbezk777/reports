"""
WSGI entry point for SAPE Reports Panel
Used by Gunicorn to run the application in production
"""
from app import app

if __name__ == "__main__":
    app.run()
