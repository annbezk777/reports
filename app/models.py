from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class SapeAccount(db.Model):
    """SAPE account model"""
    __tablename__ = 'sape_accounts'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)  # Название аккаунта для удобства
    login = db.Column(db.String(255), nullable=False)  # SAPE login (email)
    api_token = db.Column(db.String(500), nullable=False)  # SAPE API токен
    sape_user_id = db.Column(db.String(50), nullable=True)  # SAPE User ID (UID) для ссылки в ЛК
    active = db.Column(db.Boolean, default=True)
    last_sync = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    campaigns = db.relationship('Campaign', backref='account', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<SapeAccount {self.name}>'


class Client(db.Model):
    """Client model"""
    __tablename__ = 'clients'

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.String(100), nullable=False)  # ID клиента из SAPE
    name = db.Column(db.String(255), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('sape_accounts.id'), nullable=False)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    campaigns = db.relationship('Campaign', backref='client', lazy=True)

    def __repr__(self):
        return f'<Client {self.client_id}: {self.name}>'


class Campaign(db.Model):
    """Campaign model"""
    __tablename__ = 'campaigns'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.String(100), nullable=False)  # ID кампании из SAPE
    name = db.Column(db.String(255), nullable=False)
    format_type = db.Column(db.String(10), nullable=True)  # V (видео), B (баннер), TGB (ТГБ)
    account_id = db.Column(db.Integer, db.ForeignKey('sape_accounts.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)  # Link to Client
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    reports = db.relationship('ReportConfig', backref='campaign', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Campaign {self.campaign_id}: {self.name}>'


class ReportConfig(db.Model):
    """Report configuration model"""
    __tablename__ = 'report_configs'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)  # Primary campaign for display

    # Multiple campaigns support
    campaign_ids = db.Column(db.JSON, nullable=False)  # List of campaign IDs: [1, 2, 3]
    campaign_mode = db.Column(db.String(20), default='separate')  # 'separate' or 'combined'

    # Report name (optional, defaults to campaign name)
    name = db.Column(db.String(255), nullable=True)

    # Google Sheets settings
    google_sheet_url = db.Column(db.String(500), nullable=False)
    worksheet_name = db.Column(db.String(255), nullable=True)  # Название листа (если не указано - первый лист)

    # Table structure settings (auto-detected or manual)
    data_start_row = db.Column(db.Integer, nullable=True)
    date_column = db.Column(db.String(5), nullable=True)
    impressions_column = db.Column(db.String(5), nullable=True)
    reach_column = db.Column(db.String(5), nullable=True)
    clicks_column = db.Column(db.String(5), nullable=True)
    ctr_column = db.Column(db.String(5), nullable=True)
    completes_column = db.Column(db.String(5), nullable=True)  # Досмотры (для видео)
    spent_column = db.Column(db.String(5), nullable=True)

    # NEW: Campaign settings with daily and total frequencies
    # Format: {
    #   "1": {
    #     "daily_frequency": 3.0,
    #     "daily_variance": 0.1,
    #     "total_frequency": 2.5,
    #     "total_variance": 0.1
    #   }
    # }
    campaign_settings = db.Column(db.JSON, nullable=True)

    # DEPRECATED: Old frequency fields (kept for backward compatibility)
    # Will be removed in future version - use campaign_settings instead
    campaign_frequencies = db.Column(db.JSON, nullable=True)
    frequency_variance = db.Column(db.Float, default=0.1, nullable=True)
    total_reach_coefficient = db.Column(db.Float, default=0.96, nullable=True)

    # Schedule settings
    schedule_enabled = db.Column(db.Boolean, default=True)
    schedule_days = db.Column(db.String(50), nullable=True)  # "1,5" для понедельника и пятницы
    schedule_time = db.Column(db.String(10), nullable=True)  # "09:00"

    # Manager assignment
    manager = db.Column(db.String(100), nullable=True)  # Даня, Саша, Аня, Лена

    # Brand (auto-extracted from Google Sheets)
    brand = db.Column(db.String(255), nullable=True)  # Бренд, извлеченный из таблицы

    # Metadata
    last_update = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    active = db.Column(db.Boolean, default=True)
    archived = db.Column(db.Boolean, default=False)  # Archived reports hidden from main view

    # Relationships
    logs = db.relationship('ReportLog', backref='report_config', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<ReportConfig for Campaign ID {self.campaign_id}>'


class ReportLog(db.Model):
    """Report execution log"""
    __tablename__ = 'report_logs'

    id = db.Column(db.Integer, primary_key=True)
    report_config_id = db.Column(db.Integer, db.ForeignKey('report_configs.id'), nullable=False)
    executed_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), nullable=False)  # success, error
    error_message = db.Column(db.Text, nullable=True)
    metrics = db.Column(db.JSON, nullable=True)  # Сохраненные метрики

    def __repr__(self):
        return f'<ReportLog {self.id}: {self.status}>'
