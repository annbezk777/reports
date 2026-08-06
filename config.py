import os
from datetime import timedelta

class Config:
    """Application configuration"""

    # Base directory
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    # Flask secret key
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

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
