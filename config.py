import os
from datetime import timedelta

class Config:
    """Application configuration"""

    # Base directory
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    # Flask secret key
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    # Session cookie hardening - HTTPONLY blocks JS/XSS from reading the
    # cookie, SAMESITE=Lax blocks it being sent on cross-site POSTs (the
    # main CSRF vector here since there's no CSRF token yet). SECURE
    # requires HTTPS, which only prod has (local dev runs on plain HTTP) -
    # piggybacks on SECRET_KEY being set, since that's only set in the
    # prod systemd unit, never locally.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('SECRET_KEY') is not None

    # Database
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'database', 'sape_reports.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # SAPE API
    SAPE_API_URL = 'https://traffic.sape.ru/api/v2'
    SAPE_LOGIN_ENDPOINT = '/login'
    SAPE_CAMPAIGNS_ENDPOINT = '/campaigns/list'
    SAPE_STATS_ENDPOINT = '/campaigns/statistics'

    # Google Sheets API
    GOOGLE_CREDENTIALS_FILE = os.path.join(BASE_DIR, 'google_credentials.json')
    GOOGLE_SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

    # Scheduler
    SCHEDULER_API_ENABLED = False  # Отключено - обновляем вручную
    SCHEDULER_TIMEZONE = 'Europe/Moscow'
