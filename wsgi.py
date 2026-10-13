"""
WSGI entry point for Gunicorn
"""
from app import app as application

if __name__ == "__main__":
    application.run()
