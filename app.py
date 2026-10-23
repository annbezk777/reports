from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, abort
from functools import wraps
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime, timedelta
import os
import hashlib
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import logging
import sys

# Import configuration
from config import Config

# Initialize Flask app
app = Flask(__name__,
           template_folder='app/templates',
           static_folder='app/static')
app.config.from_object(Config)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('app_logs.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Also redirect print() to logger
class PrintLogger:
    def __init__(self, logger, level):
        self.logger = logger
        self.level = level

    def write(self, message):
        if message.strip():
            self.logger.log(self.level, message.strip())

    def flush(self):
        pass

# Redirect stdout to logger
sys.stdout = PrintLogger(logger, logging.INFO)

# Initialize database
from app.models import db, SapeAccount, Client, Campaign, ReportConfig, ReportLog, MonitoringCampaign, VerifierLink, VerifierLinkMapping
db.init_app(app)
migrate = Migrate(app, db)


class AsanaSyncError(Exception):
    """User-facing error raised while syncing a monitoring from Asana"""
    pass

# Import API clients
from app.api.sape_client import SapeAPIClient
from app.api.google_sheets_client import GoogleSheetsClient

# Template filters
@app.template_filter('format_month')
def format_month(date_string):
    """Format YYYY-MM-DD or YYYY-MM to Russian month name"""
    months_ru = {
        '01': 'Январь', '02': 'Февраль', '03': 'Март', '04': 'Апрель',
        '05': 'Май', '06': 'Июнь', '07': 'Июль', '08': 'Август',
        '09': 'Сентябрь', '10': 'Октябрь', '11': 'Ноябрь', '12': 'Декабрь'
    }
    try:
        parts = date_string.split('-')
        year = parts[0]
        month = parts[1]
        return f"{months_ru.get(month, month)} {year}"
    except:
        return date_string


@app.template_filter('to_moscow')
def to_moscow(dt):
    """Convert a naive UTC datetime (stored via datetime.utcnow()) to Moscow time for display"""
    if not dt:
        return dt
    return pytz.utc.localize(dt).astimezone(pytz.timezone('Europe/Moscow'))




# ==================== AUTHENTICATION ====================

# Email configuration for verification
SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
SMTP_EMAIL = os.environ.get('SMTP_EMAIL', 'noreply@sape.ru')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')

def send_verification_email(email, code):
    """Send verification code to user email"""
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_EMAIL
        msg['To'] = email
        msg['Subject'] = 'Подтверждение регистрации - SAPE Reports Panel'

        body = f"""
Здравствуйте!

Ваш код подтверждения для регистрации в SAPE Reports Panel:

{code}

Код действителен в течение 15 минут.

Если вы не регистрировались в системе, проигнорируйте это письмо.

---
SAPE Reports Panel
Автоматизация отчетов SAPE → Google Sheets
"""
        msg.attach(MIMEText(body, 'plain'))

        if SMTP_PASSWORD:
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
            server.quit()
            return True
        else:
            # For development: print code to console
            print(f"\n{'='*60}")
            print(f"VERIFICATION CODE for {email}: {code}")
            print(f"{'='*60}\n")
            return True

    except Exception as e:
        print(f"Error sending email: {e}")
        return False


def get_db_connection():
    """Get database connection"""
    import sqlite3
    conn = sqlite3.connect('database/sape_reports.db')
    conn.row_factory = sqlite3.Row
    return conn


def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


ADMIN_EMAIL = 'a.bereznyak@sape.ru'


def admin_required(f):
    """Restricts a route to ADMIN_EMAIL only. Everyone else (including
    other logged-in users) gets a plain 404, not a 403 - the feature
    shouldn't even appear to exist for them."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login', next=request.url))
        if session.get('user_email') != ADMIN_EMAIL:
            abort(404)
        return f(*args, **kwargs)
    return decorated_function


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()

        if not email.endswith('@sape.ru'):
            flash('Логин должен быть в формате: user@sape.ru', 'error')
            return render_template('login.html')

        # Check user in database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE email = ? AND active = 1', (email,))
        user = cursor.fetchone()
        conn.close()

        if user:
            # Check if email is verified
            if not user['email_verified']:
                flash('Email не подтвержден. Проверьте почту и введите код подтверждения.', 'error')
                return redirect(url_for('verify_email') + f'?email={email}')

            # Check password
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            if user['password_hash'] == password_hash:
                session['logged_in'] = True
                session['user_email'] = email
                session['user_id'] = user['id']
                session.permanent = True

                flash(f'Добро пожаловать, {email}!', 'success')

                next_page = request.args.get('next')
                if next_page:
                    return redirect(next_page)
                return redirect(url_for('index'))
            else:
                flash('Неверный пароль', 'error')
        else:
            flash('Пользователь не найден', 'error')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
@admin_required
def register():
    """Add a new user. Admin-only (requires login) - there is no public
    self-registration; the admin sets the initial password here and
    hands it to the new user directly, so the account is active
    immediately with no email-verification step."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        password_confirm = request.form.get('password_confirm', '').strip()

        # Validation
        if not email.endswith('@sape.ru'):
            flash('Email должен заканчиваться на @sape.ru', 'error')
            return redirect(url_for('register'))

        if len(password) < 6:
            flash('Пароль должен содержать минимум 6 символов', 'error')
            return redirect(url_for('register'))

        if password != password_confirm:
            flash('Пароли не совпадают', 'error')
            return redirect(url_for('register'))

        # Check if user exists
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            flash('Пользователь с таким email уже существует', 'error')
            conn.close()
            return redirect(url_for('register'))

        password_hash = hashlib.sha256(password.encode()).hexdigest()

        # Create user - active and verified immediately, since the
        # password is handed to them directly by an already-trusted admin
        cursor.execute('''
INSERT INTO users (email, password_hash, verification_code, email_verified, active)
VALUES (?, ?, NULL, 1, 1)
''', (email, password_hash))
        conn.commit()
        conn.close()

        flash(f'Пользователь {email} создан. Сообщите ему пароль лично.', 'success')
        return redirect(url_for('register'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, email, active FROM users ORDER BY email')
    users = cursor.fetchall()
    conn.close()

    return render_template('register.html', users=users)


@app.route('/verify-email', methods=['GET', 'POST'])
def verify_email():
    """Email verification page"""
    email = request.args.get('email') or request.form.get('email', '').strip()

    if request.method == 'POST':
        code = request.form.get('code', '').strip()

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE email = ? AND verification_code = ?', (email, code))
        user = cursor.fetchone()

        if user:
            # Mark email as verified
            cursor.execute('UPDATE users SET email_verified = 1, verification_code = NULL WHERE email = ?', (email,))
            conn.commit()
            conn.close()

            flash('Email успешно подтвержден! Теперь вы можете войти.', 'success')
            return redirect(url_for('login'))
        else:
            conn.close()
            flash('Неверный код подтверждения', 'error')

    return render_template('verify_email.html', email=email)


@app.route('/resend-verification', methods=['POST'])
def resend_verification():
    """Resend verification code"""
    email = request.form.get('email', '').strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE email = ? AND email_verified = 0', (email,))
    user = cursor.fetchone()

    if user:
        # Generate new code
        verification_code = str(random.randint(100000, 999999))
        cursor.execute('UPDATE users SET verification_code = ? WHERE email = ?', (verification_code, email))
        conn.commit()
        conn.close()

        if send_verification_email(email, verification_code):
            flash('Код подтверждения отправлен повторно', 'success')
        else:
            flash('Ошибка отправки email. Код: ' + verification_code, 'error')
    else:
        conn.close()
        flash('Пользователь не найден или email уже подтвержден', 'error')

    return redirect(url_for('verify_email') + f'?email={email}')


@app.route('/logout')
def logout():
    """Logout"""
    email = session.get('user_email', 'Пользователь')
    session.clear()
    flash(f'{email} вышел из системы', 'success')
    return redirect(url_for('login'))


@app.route('/users/<int:user_id>/reset-password', methods=['POST'])
@admin_required
def admin_reset_password(user_id):
    """Admin-only password reset for an existing user - replaces the old
    self-service "забыли пароль" email-code flow, which leaked the reset
    code directly in the page response whenever SMTP failed to send
    (which it always did here, since no SMTP credentials are configured).
    The admin now sets the new password directly and hands it to the
    user, same trust model as creating an account."""
    new_password = request.form.get('new_password', '').strip()

    if len(new_password) < 6:
        flash('Пароль должен содержать минимум 6 символов', 'error')
        return redirect(url_for('register'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT email FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        flash('Пользователь не найден', 'error')
        return redirect(url_for('register'))

    password_hash = hashlib.sha256(new_password.encode()).hexdigest()
    cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (password_hash, user_id))
    conn.commit()
    conn.close()

    flash(f'Пароль для {user["email"]} изменён. Сообщите его пользователю лично.', 'success')
    return redirect(url_for('register'))


# ==================== ROUTES ====================

@app.route('/')
@login_required
def index():
    """Redirect to dashboard"""
    return redirect(url_for('dashboard'))


@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard with stats and charts"""
    from collections import defaultdict
    from datetime import datetime, timedelta

    # Basic stats
    now = datetime.now()
    google_sheets_count = ReportConfig.query.filter(
        ReportConfig.google_sheet_url.isnot(None),
        ReportConfig.google_sheet_url != '',
        ReportConfig.active == True,
        ReportConfig.archived == False
    ).count()

    stats = {
        'total_accounts': SapeAccount.query.count(),
        'active_accounts': SapeAccount.query.filter_by(active=True).count(),
        'total_campaigns': Campaign.query.count(),
        'total_reports': ReportConfig.query.count(),
        'active_reports': ReportConfig.query.filter_by(active=True, archived=False).count(),
        'google_sheets': google_sheets_count,
        'now': now
    }

    # Reports by manager
    reports_by_manager = db.session.query(
        ReportConfig.manager,
        db.func.count(ReportConfig.id)
    ).filter(
        ReportConfig.active == True,
        ReportConfig.archived == False
    ).group_by(ReportConfig.manager).all()

    stats['reports_by_manager'] = dict(reports_by_manager) if reports_by_manager else {}

    # Chart data: Reports created by month (last 6 months)
    six_months_ago = now - timedelta(days=180)
    reports_by_month = db.session.query(
        db.func.strftime('%Y-%m', ReportConfig.created_at).label('month'),
        db.func.count(ReportConfig.id).label('count')
    ).filter(
        ReportConfig.created_at >= six_months_ago,
        ReportConfig.active == True,
        ReportConfig.archived == False
    ).group_by('month').order_by('month').all()

    # Prepare chart data
    month_names = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек']
    chart_labels = []
    chart_values = []
    current_month_str = now.strftime('%Y-%m')

    for month_str, count in reports_by_month:
        # Skip current month if it's less than 5 days into the month
        if month_str == current_month_str and now.day < 5:
            continue

        year, month = month_str.split('-')
        month_name = month_names[int(month) - 1]
        chart_labels.append(f"{month_name} {year}")
        chart_values.append(count)

    # If no data, show last 6 months with zeros
    if not chart_labels:
        for i in range(5, -1, -1):
            date = now - timedelta(days=i*30)
            chart_labels.append(month_names[date.month - 1])
            chart_values.append(0)

    chart_data = {
        'labels': chart_labels,
        'data': chart_values
    }

    # Recent activity
    recent_activity = []
    recent_logs = ReportLog.query.order_by(ReportLog.executed_at.desc()).limit(10).all()

    for log in recent_logs:
        if log.report_config:
            recent_activity.append({
                'report_name': log.report_config.name or f"Отчет #{log.report_config.id}",
                'last_update': log.executed_at,
                'status': log.status
            })

    return render_template('dashboard.html',
                         stats=stats,
                         chart_data=chart_data,
                         recent_activity=recent_activity)


@app.route('/accounts')
@login_required
def accounts():
    """List of SAPE accounts"""
    search_query = request.args.get('search', '').strip()
    
    if search_query:
        # Search in account name, login, and campaign names
        search_pattern = f'%{search_query}%'
        all_accounts = SapeAccount.query.filter(
            db.or_(
                SapeAccount.name.ilike(search_pattern),
                SapeAccount.login.ilike(search_pattern),
                SapeAccount.campaigns.any(Campaign.name.ilike(search_pattern))
            )
        ).all()
    else:
        all_accounts = SapeAccount.query.all()
    
    return render_template('accounts.html', accounts=all_accounts)


@app.route('/accounts/add', methods=['GET', 'POST'])
def add_account():
    """Add new SAPE account"""
    if request.method == 'POST':
        name = request.form.get('name')
        login = request.form.get('login')
        api_token = request.form.get('api_token')
        sape_user_id = request.form.get('sape_user_id')

        if not name or not login or not api_token:
            flash('Все поля обязательны для заполнения', 'error')
            return render_template('add_account.html')

        # Create new account
        account = SapeAccount(
            name=name,
            login=login,
            api_token=api_token,
            sape_user_id=sape_user_id if sape_user_id else None
        )

        db.session.add(account)
        db.session.commit()

        flash(f'Аккаунт "{name}" успешно добавлен. Начинается синхронизация кампаний...', 'success')
        # Automatically sync campaigns for the new account
        return redirect(url_for('sync_campaigns', account_id=account.id))

    return render_template('add_account.html')


@app.route('/accounts/<int:account_id>/edit', methods=['GET', 'POST'])
def edit_account(account_id):
    """Edit SAPE account"""
    account = SapeAccount.query.get_or_404(account_id)

    if request.method == 'POST':
        name = request.form.get('name')
        login = request.form.get('login')
        api_token = request.form.get('api_token')
        sape_user_id = request.form.get('sape_user_id')

        if not name or not login or not api_token:
            flash('Все поля обязательны для заполнения', 'error')
            return render_template('edit_account.html', account=account)

        account.name = name
        account.login = login
        account.api_token = api_token
        account.sape_user_id = sape_user_id if sape_user_id else None

        db.session.commit()

        flash(f'Аккаунт "{name}" успешно обновлен', 'success')
        return redirect(url_for('accounts'))

    return render_template('edit_account.html', account=account)


def detect_campaign_format(campaign_name, sape_type=None):
    """
    Detect campaign format from SAPE API type or name

    Args:
        campaign_name: Campaign name for fallback detection
        sape_type: SAPE API campaign type (integer)
            3 = Banner
            6 = Video (OLV/CTV)
            7 = TGB (Telegram)

    Returns:
        Format code: 'B', 'V', 'CTV', or 'TGB'
    """
    # Use SAPE API type if available
    if sape_type is not None:
        if sape_type == 7:
            return 'TGB'
        elif sape_type == 6:
            # Type 6 is video - check name to distinguish OLV from CTV
            name_lower = campaign_name.lower()
            if 'ctv' in name_lower or 'connected tv' in name_lower:
                return 'CTV'
            else:
                return 'V'  # Default to OLV for type 6
        elif sape_type == 3:
            return 'B'
        # Unknown type - fallback to name analysis

    # Fallback: analyze campaign name
    name_lower = campaign_name.lower()

    # Check for CTV first (more specific)
    if any(keyword in name_lower for keyword in ['ctv', 'connected tv']):
        return 'CTV'

    # Check for video keywords
    if any(keyword in name_lower for keyword in ['видео', 'video', 'ютуб', 'youtube', 'vk video', 'рутуб', 'olv']):
        return 'V'

    # Check for TGB keywords
    if any(keyword in name_lower for keyword in ['тгб', 'tgb', 'telegram', 'тг ']):
        return 'TGB'

    # Default to banner
    return 'B'


@app.route('/accounts/<int:account_id>/sync')
def sync_campaigns(account_id):
    """Show progress page for single account sync"""
    account = SapeAccount.query.get_or_404(account_id)
    return render_template('sync_single_progress.html', account=account)


@app.route('/accounts/<int:account_id>/sync/execute')
def execute_sync_single(account_id):
    """Execute sync for single account and return progress as JSON"""
    from flask import Response
    import json

    def generate():
        with app.app_context():
            account = SapeAccount.query.get_or_404(account_id)

            yield f"data: {json.dumps({'type': 'start', 'account': account.name})}\n\n"

            result = sync_single_account(account)

            if result['success']:
                yield f"data: {json.dumps({'type': 'complete', 'success': True, 'clients': result.get('clients_synced', 0), 'new': result.get('campaigns_new', 0), 'updated': result.get('campaigns_updated', 0)})}\n\n"
            else:
                error_msg = result.get('error', 'Unknown error')
                yield f"data: {json.dumps({'type': 'complete', 'success': False, 'error': error_msg})}\n\n"

    return Response(generate(), mimetype='text/event-stream')


@app.route('/accounts/<int:account_id>/sync-old')
def sync_campaigns_old(account_id):
    """Sync campaigns from SAPE (old synchronous version)"""
    account = SapeAccount.query.get_or_404(account_id)

    # Initialize SAPE client with login and token
    client = SapeAPIClient(login=account.login, token=account.api_token)

    # Authenticate first
    print(f"🔐 Authenticating account: {account.login}")
    if not client.authenticate():
        print(f"❌ Authentication failed for {account.login}")
        flash('Ошибка авторизации в SAPE. Проверьте логин и токен.', 'error')
        return redirect(url_for('accounts'))

    print(f"✅ Authentication successful for {account.login}")

    # Step 1: Sync clients first
    print(f"📥 Fetching clients...")
    clients_data = client.get_clients()
    clients_synced = 0

    if clients_data:
        print(f"📋 Received {len(clients_data)} clients")
        for cl in clients_data:
            # Check if client exists
            existing_client = Client.query.filter_by(
                account_id=account.id,
                client_id=str(cl['id'])
            ).first()

            if not existing_client:
                new_client = Client(
                    account_id=account.id,
                    client_id=str(cl['id']),
                    name=cl.get('name', f"Client {cl['id']}")
                )
                db.session.add(new_client)
                clients_synced += 1
            else:
                # Update name if changed
                existing_client.name = cl.get('name', existing_client.name)

        db.session.commit()
        print(f"✅ Synced {clients_synced} clients")

    # Step 2: Get campaigns
    print(f"📥 Fetching campaigns...")
    campaigns_data = client.get_campaigns()

    if not campaigns_data:
        print(f"❌ No campaigns data returned")
        flash('Не удалось получить список кампаний.', 'error')
        return redirect(url_for('accounts'))

    print(f"📋 Received {len(campaigns_data)} campaigns")

    # Step 3: Save campaigns with client links
    synced_count = 0
    updated_count = 0

    for camp in campaigns_data:
        campaign_name = camp.get('name', f"Campaign {camp['id']}")

        # Check if campaign exists first
        campaign = Campaign.query.filter_by(
            account_id=account.id,
            campaign_id=str(camp['id'])
        ).first()

        if not campaign:
            # NEW CAMPAIGN: Get detailed info to fetch clientId and type
            campaign_detail = client.get_campaign_detail(camp['id'])
            sape_client_id = None
            sape_type = None
            if campaign_detail:
                sape_client_id = campaign_detail.get('clientId')
                sape_type = campaign_detail.get('type')

            # Detect format using SAPE API type (preferred) or name (fallback)
            format_type = detect_campaign_format(campaign_name, sape_type)

            # Find client in our DB
            db_client = None
            if sape_client_id:
                db_client = Client.query.filter_by(
                    account_id=account.id,
                    client_id=str(sape_client_id)
                ).first()

            campaign = Campaign(
                account_id=account.id,
                campaign_id=str(camp['id']),
                name=campaign_name,
                format_type=format_type,
                client_id=db_client.id if db_client else None
            )
            db.session.add(campaign)
            synced_count += 1
        else:
            # EXISTING CAMPAIGN: Just update name, skip expensive API call
            campaign.name = campaign_name
            updated_count += 1

    # Update last sync time
    account.last_sync = datetime.utcnow()
    db.session.commit()

    flash(f'Синхронизировано: {clients_synced} клиентов, {synced_count} новых кампаний, обновлено {updated_count} кампаний', 'success')
    return redirect(url_for('accounts'))


@app.route('/accounts/<int:account_id>/toggle', methods=['POST'])
def toggle_account_status(account_id):
    """Toggle account active/inactive status"""
    account = SapeAccount.query.get_or_404(account_id)

    data = request.get_json()
    account.active = data.get('active', True)

    try:
        db.session.commit()
        status_text = "активирован" if account.active else "деактивирован"
        logging.info(f"Account {account.name} ({account.login}) {status_text}")
        return jsonify({'success': True, 'active': account.active})
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error toggling account status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


def sync_single_account(account):
    """Sync campaigns for a single account (used by scheduler and bulk sync)"""
    try:
        print(f"\n{'='*60}")
        print(f"🔄 Starting sync for account: {account.name} ({account.login})")
        print(f"{'='*60}")

        # Initialize SAPE client
        client = SapeAPIClient(login=account.login, token=account.api_token)

        # Authenticate
        if not client.authenticate():
            print(f"❌ Authentication failed for {account.login}")
            return {'success': False, 'error': 'Authentication failed'}

        print(f"✅ Authentication successful")

        # Sync clients
        print(f"📥 Fetching clients...")
        clients_data = client.get_clients()
        clients_synced = 0

        if clients_data:
            print(f"📋 Received {len(clients_data)} clients")
            for cl in clients_data:
                existing_client = Client.query.filter_by(
                    account_id=account.id,
                    client_id=str(cl['id'])
                ).first()

                if not existing_client:
                    new_client = Client(
                        account_id=account.id,
                        client_id=str(cl['id']),
                        name=cl.get('name', f"Client {cl['id']}")
                    )
                    db.session.add(new_client)
                    clients_synced += 1
                else:
                    existing_client.name = cl.get('name', existing_client.name)

            db.session.commit()
            print(f"✅ Synced {clients_synced} new clients")

        # Sync campaigns
        print(f"📥 Fetching campaigns...")
        campaigns_data = client.get_campaigns()

        if not campaigns_data:
            print(f"❌ No campaigns data returned")
            return {'success': False, 'error': 'No campaigns data'}

        print(f"📋 Received {len(campaigns_data)} campaigns")

        synced_count = 0
        updated_count = 0

        for camp in campaigns_data:
            campaign_name = camp.get('name', f"Campaign {camp['id']}")

            # Check if campaign exists first
            campaign = Campaign.query.filter_by(
                account_id=account.id,
                campaign_id=str(camp['id'])
            ).first()

            if not campaign:
                # NEW CAMPAIGN: Get detailed info (this is slow, only for new campaigns)
                campaign_detail = client.get_campaign_detail(camp['id'])
                sape_client_id = None
                sape_type = None
                if campaign_detail:
                    sape_client_id = campaign_detail.get('clientId')
                    sape_type = campaign_detail.get('type')

                # Detect format using SAPE API type (preferred) or name (fallback)
                format_type = detect_campaign_format(campaign_name, sape_type)

                # Find client in DB
                db_client = None
                if sape_client_id:
                    db_client = Client.query.filter_by(
                        account_id=account.id,
                        client_id=str(sape_client_id)
                    ).first()

                campaign = Campaign(
                    account_id=account.id,
                    campaign_id=str(camp['id']),
                    name=campaign_name,
                    format_type=format_type,
                    client_id=db_client.id if db_client else None
                )
                db.session.add(campaign)
                synced_count += 1
            else:
                # EXISTING CAMPAIGN: Just update name (fast, no API call)
                campaign.name = campaign_name
                updated_count += 1

        # Update last sync time
        account.last_sync = datetime.utcnow()
        db.session.commit()

        print(f"✅ Sync completed: {clients_synced} clients, {synced_count} new campaigns, {updated_count} updated")
        print(f"{'='*60}\n")

        return {
            'success': True,
            'clients_synced': clients_synced,
            'campaigns_new': synced_count,
            'campaigns_updated': updated_count
        }

    except Exception as e:
        print(f"❌ Error syncing account {account.login}: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}


@app.route('/accounts/sync-all')
def sync_all_accounts():
    """Sync all active accounts - show progress page"""
    accounts = SapeAccount.query.filter_by(active=True).all()

    if not accounts:
        flash('Нет активных аккаунтов для синхронизации', 'warning')
        return redirect(url_for('accounts'))

    # Show progress page with account list
    return render_template('sync_progress.html',
                         accounts=accounts,
                         total=len(accounts))


@app.route('/accounts/sync-all/execute')
def execute_sync_all():
    """Execute sync and return progress as JSON"""
    from flask import Response
    import json

    def generate():
        with app.app_context():
            accounts = SapeAccount.query.filter_by(active=True).all()

            yield f"data: {json.dumps({'type': 'start', 'total': len(accounts)})}\n\n"

            total_clients = 0
            total_new_campaigns = 0
            total_updated_campaigns = 0
            failed_accounts = []

            for idx, account in enumerate(accounts, 1):
                # Send progress update
                yield f"data: {json.dumps({'type': 'progress', 'current': idx, 'total': len(accounts), 'account': account.name})}\n\n"

                result = sync_single_account(account)

            if result['success']:
                total_clients += result.get('clients_synced', 0)
                total_new_campaigns += result.get('campaigns_new', 0)
                total_updated_campaigns += result.get('campaigns_updated', 0)

                yield f"data: {json.dumps({'type': 'account_success', 'account': account.name, 'clients': result.get('clients_synced', 0), 'new': result.get('campaigns_new', 0), 'updated': result.get('campaigns_updated', 0)})}\n\n"
            else:
                error_msg = result.get('error', 'Unknown error')
                failed_accounts.append(f"{account.name}: {error_msg}")
                yield f"data: {json.dumps({'type': 'account_error', 'account': account.name, 'error': error_msg})}\n\n"

        # Send completion
        yield f"data: {json.dumps({'type': 'complete', 'total_clients': total_clients, 'total_new': total_new_campaigns, 'total_updated': total_updated_campaigns, 'failed': failed_accounts, 'success_count': len(accounts) - len(failed_accounts)})}\n\n"

    return Response(generate(), mimetype='text/event-stream')


@app.route('/accounts/sync-all-simple')
def sync_all_accounts_simple():
    """Sync all active accounts - simple version without progress"""
    accounts = SapeAccount.query.filter_by(active=True).all()

    if not accounts:
        flash('Нет активных аккаунтов для синхронизации', 'warning')
        return redirect(url_for('accounts'))

    print(f"\n🔄 Starting bulk sync for {len(accounts)} accounts...")

    total_clients = 0
    total_new_campaigns = 0
    total_updated_campaigns = 0
    failed_accounts = []

    for account in accounts:
        result = sync_single_account(account)

        if result['success']:
            total_clients += result.get('clients_synced', 0)
            total_new_campaigns += result.get('campaigns_new', 0)
            total_updated_campaigns += result.get('campaigns_updated', 0)
        else:
            failed_accounts.append(f"{account.name}: {result.get('error', 'Unknown error')}")

    # Build flash message
    success_msg = f'✅ Синхронизировано {len(accounts) - len(failed_accounts)} из {len(accounts)} аккаунтов: '
    success_msg += f'{total_clients} клиентов, {total_new_campaigns} новых кампаний, {total_updated_campaigns} обновлено'

    if failed_accounts:
        flash(success_msg, 'success')
        flash(f'⚠️ Ошибки: ' + '; '.join(failed_accounts), 'warning')
    else:
        flash(success_msg, 'success')

    return redirect(url_for('accounts'))


def get_last_sync_time():
    """Get timestamp of last successful sync"""
    sync_file = '.last_sync'
    try:
        if os.path.exists(sync_file):
            with open(sync_file, 'r') as f:
                timestamp_str = f.read().strip()
                return datetime.fromisoformat(timestamp_str)
    except Exception as e:
        logging.warning(f"Could not read last sync time: {e}")
    return None


def update_last_sync_time():
    """Update timestamp of last successful sync"""
    sync_file = '.last_sync'
    try:
        with open(sync_file, 'w') as f:
            f.write(datetime.now().isoformat())
    except Exception as e:
        logging.warning(f"Could not update last sync time: {e}")


def should_sync_on_startup():
    """Check if we should sync on startup (if last sync was >24h ago)"""
    last_sync = get_last_sync_time()
    if last_sync is None:
        logging.info("📋 No previous sync found - will sync on startup")
        return True

    hours_since_sync = (datetime.now() - last_sync).total_seconds() / 3600
    logging.info(f"📋 Last sync: {last_sync.strftime('%Y-%m-%d %H:%M:%S')} ({hours_since_sync:.1f} hours ago)")

    if hours_since_sync >= 24:
        logging.info("✅ More than 24 hours since last sync - will sync on startup")
        return True
    else:
        logging.info(f"⏭️ Last sync was recent ({hours_since_sync:.1f}h ago) - skipping startup sync")
        return False


def scheduled_sync_all_accounts():
    """Scheduled task to sync all accounts (runs at 10:00 daily or on startup if needed)"""
    with app.app_context():
        logging.info(f"\n{'='*60}")
        logging.info(f"⏰ SCHEDULED SYNC - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logging.info(f"{'='*60}")

        accounts = SapeAccount.query.filter_by(active=True).all()

        if not accounts:
            logging.info("ℹ️ No active accounts to sync")
            return

        logging.info(f"🔄 Syncing {len(accounts)} accounts...")

        total_clients = 0
        total_new_campaigns = 0
        total_updated_campaigns = 0

        for account in accounts:
            result = sync_single_account(account)

            if result['success']:
                total_clients += result.get('clients_synced', 0)
                total_new_campaigns += result.get('campaigns_new', 0)
                total_updated_campaigns += result.get('campaigns_updated', 0)

            # Add delay between accounts to avoid rate limiting
            import time
            time.sleep(3)  # 3 seconds delay between each account sync

        logging.info(f"\n✅ SCHEDULED SYNC COMPLETED:")
        logging.info(f"   Total clients: {total_clients}")
        logging.info(f"   New campaigns: {total_new_campaigns}")
        logging.info(f"   Updated campaigns: {total_updated_campaigns}")
        logging.info(f"{'='*60}\n")

        # Update last sync timestamp
        update_last_sync_time()


@app.route('/reports')
@login_required
def reports():
    """List of report configurations"""
    # Check if user wants to see archived reports
    show_archived = request.args.get('show_archived', 'false').lower() == 'true'

    # Get manager filter from URL or session
    manager_filter = request.args.get('manager', None)

    print(f"🔍 DEBUG reports(): manager_filter from URL: {manager_filter}")
    print(f"🔍 DEBUG reports(): session before: {dict(session)}")

    # If manager filter provided in URL, save to session
    if manager_filter is not None:
        session['manager_filter'] = manager_filter
        session.modified = True  # Mark session as modified to ensure it's saved
        print(f"🔍 DEBUG reports(): Saved to session: {manager_filter}")
    else:
        # Use filter from session if available
        manager_filter = session.get('manager_filter', '')
        print(f"🔍 DEBUG reports(): Retrieved from session: {manager_filter}")

    print(f"🔍 DEBUG reports(): session after: {dict(session)}")
    print(f"🔍 DEBUG reports(): final manager_filter: {manager_filter}")

    # Build query
    query = ReportConfig.query.join(Campaign)

    # Apply archived filter
    if show_archived:
        query = query.filter(ReportConfig.archived == True)
    else:
        query = query.filter(ReportConfig.archived == False)

    # Apply manager filter
    if manager_filter:
        if manager_filter == 'unassigned':
            query = query.filter((ReportConfig.manager == None) | (ReportConfig.manager == ''))
        else:
            query = query.filter(ReportConfig.manager == manager_filter)

    all_reports = query.all()

    # Get unique months from reports for filter
    months_set = set()
    for report in all_reports:
        if report.created_at:
            month_year = report.created_at.strftime('%Y-%m')
            months_set.add(month_year)

    # Sort months in descending order (newest first)
    months_list = sorted(list(months_set), reverse=True)

    # Get all accounts for the modal form
    accounts = SapeAccount.query.filter_by(active=True).order_by(SapeAccount.name).all()

    return render_template('reports.html',
                         reports=all_reports,
                         show_archived=show_archived,
                         manager_filter=manager_filter,
                         accounts=accounts,
                         months_list=months_list)


# ============================================================================
# MONITORING ROUTES
# ============================================================================

@app.route('/monitoring')
@login_required
def monitoring():
    """List of monitoring campaigns"""
    # Get manager filter from URL or session
    manager_filter = request.args.get('manager', None)
    show_archived = request.args.get('show_archived', 'false').lower() == 'true'

    # Build query
    query = MonitoringCampaign.query.filter(MonitoringCampaign.archived == show_archived)

    # Apply manager filter
    if manager_filter:
        if manager_filter == 'unassigned':
            query = query.filter((MonitoringCampaign.manager == None) | (MonitoringCampaign.manager == ''))
        else:
            query = query.filter(MonitoringCampaign.manager == manager_filter)

    all_monitorings = query.order_by(MonitoringCampaign.created_at.desc()).all()

    # Get all accounts for the form
    accounts = SapeAccount.query.filter_by(active=True).order_by(SapeAccount.name).all()

    return render_template('monitoring.html',
                         monitorings=all_monitorings,
                         manager_filter=manager_filter,
                         show_archived=show_archived,
                         accounts=accounts)


@app.route('/monitoring/<int:monitoring_id>')
@login_required
def monitoring_detail(monitoring_id):
    """Monitoring campaign detail page"""
    monitoring = MonitoringCampaign.query.get_or_404(monitoring_id)
    return render_template('monitoring_detail.html', monitoring=monitoring)


@app.route('/monitoring/<int:monitoring_id>/archive', methods=['POST'])
@login_required
def archive_monitoring(monitoring_id):
    """Archive monitoring campaign"""
    monitoring = MonitoringCampaign.query.get_or_404(monitoring_id)
    monitoring.archived = True
    db.session.commit()
    flash('Мониторинг перемещен в архив', 'success')
    return redirect(url_for('monitoring'))


@app.route('/monitoring/<int:monitoring_id>/unarchive', methods=['POST'])
@login_required
def unarchive_monitoring(monitoring_id):
    """Unarchive monitoring campaign"""
    monitoring = MonitoringCampaign.query.get_or_404(monitoring_id)
    monitoring.archived = False
    db.session.commit()
    flash('Мониторинг восстановлен из архива', 'success')
    return redirect(url_for('monitoring'))


@app.route('/monitoring/<int:monitoring_id>/copy')
@login_required
def copy_monitoring(monitoring_id):
    """Copy monitoring campaign with all settings"""
    original = MonitoringCampaign.query.get_or_404(monitoring_id)

    # Create a copy with all plan settings, but reset fact data
    new_monitoring = MonitoringCampaign(
        name=f"{original.name} (копия)",
        account_id=original.account_id,
        campaign_ids=original.campaign_ids,
        date_from=original.date_from,
        date_to=original.date_to,
        plan_impressions=original.plan_impressions,
        plan_clicks=original.plan_clicks,
        plan_visits=original.plan_visits,
        plan_conversions=original.plan_conversions,
        plan_bounce_rate=original.plan_bounce_rate,
        plan_page_depth=original.plan_page_depth,
        plan_robotness=original.plan_robotness,
        plan_time_on_site=original.plan_time_on_site,
        plan_pi=original.plan_pi,
        plan_ivt_impressions=original.plan_ivt_impressions,
        plan_givt_impressions=original.plan_givt_impressions,
        plan_sivt=original.plan_sivt,
        plan_givt_clicks=original.plan_givt_clicks,
        plan_vtr=original.plan_vtr,
        metrika_counter_id=original.metrika_counter_id,
        metrika_goal_id=original.metrika_goal_id,
        utm_source=original.utm_source,
        utm_campaign=original.utm_campaign,
        manager=original.manager,
        google_sheet_url=original.google_sheet_url,
        # Reset all fact data
        fact_impressions=None,
        fact_clicks=None,
        fact_visits=None,
        fact_bounce_rate=None,
        fact_time_on_site=None,
        fact_page_depth=None,
        fact_robotness=None,
        fact_ivt_impressions=None,
        fact_givt_impressions=None,
        fact_sivt_impressions=None,
        fact_givt_clicks=None,
        fact_vtr=None,
        last_sync=None,
        active=True,
        archived=False
    )

    db.session.add(new_monitoring)
    db.session.commit()

    flash(f'Создана копия мониторинга "{original.name}".', 'success')
    return redirect(url_for('monitoring'))


@app.route('/monitoring/<int:monitoring_id>/delete', methods=['POST'])
@login_required
def delete_monitoring(monitoring_id):
    """Delete monitoring campaign"""
    monitoring = MonitoringCampaign.query.get_or_404(monitoring_id)
    monitoring_name = monitoring.name
    db.session.delete(monitoring)
    db.session.commit()
    flash(f'Мониторинг "{monitoring_name}" удален', 'success')
    return redirect(url_for('monitoring'))


@app.route('/monitoring/bulk-archive', methods=['POST'])
@login_required
def bulk_archive_monitorings():
    """Archive multiple monitoring campaigns at once"""
    monitoring_ids = (request.get_json(silent=True) or {}).get('monitoring_ids', [])
    count = 0
    for m in MonitoringCampaign.query.filter(MonitoringCampaign.id.in_(monitoring_ids)).all():
        m.archived = True
        count += 1
    db.session.commit()
    return jsonify({'success': True, 'count': count})


@app.route('/monitoring/bulk-delete', methods=['POST'])
@login_required
def bulk_delete_monitorings():
    """Permanently delete multiple monitoring campaigns at once"""
    monitoring_ids = (request.get_json(silent=True) or {}).get('monitoring_ids', [])
    count = 0
    for m in MonitoringCampaign.query.filter(MonitoringCampaign.id.in_(monitoring_ids)).all():
        db.session.delete(m)
        count += 1
    db.session.commit()
    return jsonify({'success': True, 'count': count})


def _sync_monitoring_from_asana(monitoring):
    """Pull media-plan target fields from the linked Asana task onto
    `monitoring`. Returns a result dict (not yet committed) or raises
    AsanaSyncError with a user-facing message."""
    from app.api.asana_client import AsanaClient

    if not monitoring.asana_task_url:
        raise AsanaSyncError('У мониторинга не указана ссылка на задачу Asana')

    client = AsanaClient()
    task_gid = client.extract_task_gid(monitoring.asana_task_url)
    if not task_gid:
        raise AsanaSyncError('Не удалось распознать ID задачи из ссылки')

    try:
        task = client.get_task(task_gid)
    except Exception as e:
        logger.error(f"Error fetching Asana task {task_gid}: {e}")
        raise AsanaSyncError(f'Ошибка запроса к Asana: {e}')

    # Use THIS monitoring's own format(s) (from its SAPE campaigns) to pick
    # which показы/клики slot(s) to read, rather than the task's own
    # "Формат" field - that field can have multiple formats selected
    # (one task covering several monitorings) or simply be filled in
    # wrong, since it's manual.
    monitoring_campaigns = monitoring.get_campaigns()
    format_indices = sorted(set(
        AsanaClient.format_index_for_campaign_type(c.format_type) for c in monitoring_campaigns
    )) if monitoring_campaigns else []

    if len(format_indices) > 1:
        # This one monitoring bundles campaigns of several different
        # formats (e.g. video + banner) - показы/клики each live in their
        # own semicolon slot in Asana, so reading just one slot (e.g. the
        # format of whichever campaign happens to be first) silently
        # drops the rest, down to 0 if that one slot is empty. Sum across
        # every format this monitoring actually has campaigns in instead.
        parsed = None
        total_impressions = 0
        total_clicks = 0
        for idx in format_indices:
            parsed_for_idx = client.parse_monitoring_fields(task, format_idx=idx)
            if parsed is None:
                parsed = parsed_for_idx  # non-format-specific fields (dates, PI, VTR, KPI...) are the same regardless of idx
            total_impressions += parsed_for_idx.get('impressions', 0) or 0
            total_clicks += parsed_for_idx.get('clicks', 0) or 0
        parsed['impressions'] = total_impressions
        parsed['clicks'] = total_clicks
    else:
        format_idx = format_indices[0] if format_indices else None
        parsed = client.parse_monitoring_fields(task, format_idx=format_idx)

    # A single Asana task can cover a media plan that spans several
    # months while a monitoring only tracks one of them (e.g. task is
    # 14.09-31.10, monitoring is just October) - показы/клики are totals
    # for the task's whole period, so prorate them down to the overlap
    # with this monitoring's own date_from/date_to.
    task_date_from = parsed.get('task_date_from')
    task_date_to = parsed.get('task_date_to')
    prorated = False
    if task_date_from and task_date_to and (task_date_from != monitoring.date_from or task_date_to != monitoring.date_to):
        for key in ('impressions', 'clicks'):
            if key in parsed:
                prorated_value = AsanaClient.prorate_to_period(
                    parsed[key], task_date_from, task_date_to, monitoring.date_from, monitoring.date_to
                )
                if prorated_value != parsed[key]:
                    prorated = True
                parsed[key] = prorated_value

    field_map = {
        'impressions': 'plan_impressions',
        'clicks': 'plan_clicks',
        'pi': 'plan_pi',
        'bounce': 'plan_bounce_rate',
        'time': 'plan_time_on_site',
        'depth': 'plan_page_depth',
        'robotness': 'plan_robotness',
    }
    # Asana only tracks VTR (video completion rate). For video monitorings
    # that's exactly what the "VTR" column shows, so map it across. For
    # banner/TGB monitorings that same DB slot is displayed as "VR"
    # (viewability rate) - a different metric Asana doesn't provide, so
    # don't overwrite it with VTR data.
    if monitoring.is_video_format():
        field_map['vtr'] = 'plan_vtr'

    updated_fields = []
    for key, attr in field_map.items():
        if key in parsed:
            value = parsed[key]
            if attr in ('plan_impressions', 'plan_clicks'):
                value = int(value)
            setattr(monitoring, attr, value)
            updated_fields.append(attr)

    if 'kpi_comment' in parsed:
        monitoring.asana_kpi_comment = parsed['kpi_comment']
        updated_fields.append('asana_kpi_comment')

    # Визиты = клики × PI, same calculation the edit form does client-side -
    # recompute here too since this sync path bypasses that JS entirely.
    if ('plan_clicks' in updated_fields or 'plan_pi' in updated_fields) and monitoring.plan_clicks and monitoring.plan_pi:
        monitoring.plan_visits = round(monitoring.plan_clicks * (monitoring.plan_pi / 100))
        updated_fields.append('plan_visits')

    if not updated_fields:
        raise AsanaSyncError('Не удалось распознать ни одного поля в задаче Asana')

    logger.info(f"✅ Synced monitoring {monitoring.id} from Asana task {task_gid}: {updated_fields}")

    return {
        'task_name': parsed.get('task_name'),
        'format': parsed.get('format'),
        'updated_fields': updated_fields,
        'prorated': prorated,
    }


@app.route('/monitoring/<int:monitoring_id>/sync-asana', methods=['POST'])
@login_required
def sync_monitoring_from_asana(monitoring_id):
    """Explicit manual re-pull of the media plan from the linked Asana
    task. This is the ONLY way to re-sync besides changing the link
    itself - deliberately not tied to the regular SAPE "Обновить сейчас"
    fact refresh, and deliberately not triggered implicitly on every
    edit save, so it never silently overwrites manual corrections.

    Also accepts the Asana link field's current value even if the main
    form hasn't been saved yet, and saves it first - so pasting a link
    and clicking "Обновить" works in one click instead of failing with
    "ссылка не указана"."""
    monitoring = MonitoringCampaign.query.get_or_404(monitoring_id)

    submitted_url = request.form.get('asana_task_url')
    if submitted_url and submitted_url != monitoring.asana_task_url:
        monitoring.asana_task_url = submitted_url
        db.session.commit()

    try:
        result = _sync_monitoring_from_asana(monitoring)
    except AsanaSyncError as e:
        return jsonify({'success': False, 'error': str(e)}), 400

    db.session.commit()

    return jsonify({'success': True, **result})


@app.route('/monitoring/create', methods=['POST'])
@login_required
def create_monitoring():
    """Create new monitoring campaign"""
    try:
        # Get form data
        name = request.form.get('name')
        account_id = request.form.get('account_id')
        campaign_ids = request.form.getlist('campaign_ids')  # Multiple values
        date_from = request.form.get('date_from')
        date_to = request.form.get('date_to')

        # Media plan
        plan_impressions = request.form.get('plan_impressions')
        plan_clicks = request.form.get('plan_clicks')

        # Post-click KPIs
        plan_visits = request.form.get('plan_visits')
        plan_conversions = request.form.get('plan_conversions')
        plan_bounce_rate = request.form.get('plan_bounce_rate')
        plan_time_on_site = request.form.get('plan_time_on_site')
        plan_page_depth = request.form.get('plan_page_depth')
        plan_robotness = request.form.get('plan_robotness')

        # Traffic quality & IVT
        plan_pi = request.form.get('plan_pi')
        plan_vtr = request.form.get('plan_vtr')
        logger.info(f"📝 CREATE - plan_vtr from form: '{plan_vtr}' (type: {type(plan_vtr).__name__})")
        plan_ivt = request.form.get('plan_ivt_impressions')
        plan_givt = request.form.get('plan_givt_impressions')
        plan_sivt = request.form.get('plan_sivt')
        plan_givt_clicks = request.form.get('plan_givt_clicks')

        # Manager
        manager = request.form.get('manager')

        # Convert campaign IDs to integers
        campaign_ids = [int(cid) for cid in campaign_ids if cid]

        # Create monitoring
        monitoring = MonitoringCampaign(
            name=name,
            account_id=int(account_id),
            campaign_ids=campaign_ids,
            date_from=datetime.strptime(date_from, '%Y-%m-%d').date(),
            date_to=datetime.strptime(date_to, '%Y-%m-%d').date(),
            plan_impressions=int(plan_impressions) if plan_impressions else None,
            plan_clicks=int(plan_clicks) if plan_clicks else None,
            plan_visits=int(plan_visits) if plan_visits else None,
            plan_conversions=int(plan_conversions) if plan_conversions else None,
            plan_bounce_rate=float(plan_bounce_rate) if plan_bounce_rate else None,
            plan_time_on_site=float(plan_time_on_site) if plan_time_on_site else None,
            plan_page_depth=float(plan_page_depth) if plan_page_depth else None,
            plan_robotness=float(plan_robotness) if plan_robotness else None,
            plan_pi=float(plan_pi) if plan_pi else None,
            plan_vtr=int(round(float(plan_vtr))) if plan_vtr else None,
            plan_ivt_impressions=float(plan_ivt) if plan_ivt else None,
            plan_givt_impressions=float(plan_givt) if plan_givt else None,
            plan_sivt=float(plan_sivt) if plan_sivt else None,
            plan_givt_clicks=float(plan_givt_clicks) if plan_givt_clicks else None,
            manager=manager if manager else None
        )

        asana_task_url = request.form.get('asana_task_url')
        monitoring.asana_task_url = asana_task_url if asana_task_url else None

        targetads_report_url = request.form.get('targetads_report_url', '').strip()
        monitoring.targetads_report_url = targetads_report_url if targetads_report_url else None

        db.session.add(monitoring)
        db.session.commit()

        asana_warning = None
        if monitoring.asana_task_url:
            try:
                _sync_monitoring_from_asana(monitoring)
                db.session.commit()
            except AsanaSyncError as e:
                asana_warning = str(e)

        if asana_warning:
            flash(f'Мониторинг создан, но не удалось подтянуть план из Asana: {asana_warning}', 'error')
        else:
            flash('Мониторинг успешно создан', 'success')
        return redirect(url_for('monitoring'))

    except Exception as e:
        logger.error(f"Error creating monitoring: {e}")
        flash(f'Ошибка создания мониторинга: {str(e)}', 'error')
        return redirect(url_for('monitoring'))


@app.route('/monitoring/<int:monitoring_id>/edit', methods=['POST'])
@login_required
def edit_monitoring(monitoring_id):
    """Update monitoring campaign"""
    try:
        monitoring = MonitoringCampaign.query.get_or_404(monitoring_id)

        # Update fields
        monitoring.name = request.form.get('name')
        monitoring.account_id = int(request.form.get('account_id'))

        campaign_ids = request.form.getlist('campaign_ids')
        monitoring.campaign_ids = [int(cid) for cid in campaign_ids if cid]

        date_from = request.form.get('date_from')
        date_to = request.form.get('date_to')
        monitoring.date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
        monitoring.date_to = datetime.strptime(date_to, '%Y-%m-%d').date()

        # Media plan
        plan_impressions = request.form.get('plan_impressions')
        plan_clicks = request.form.get('plan_clicks')
        monitoring.plan_impressions = int(plan_impressions) if plan_impressions else None
        monitoring.plan_clicks = int(plan_clicks) if plan_clicks else None

        # Post-click KPIs
        plan_visits = request.form.get('plan_visits')
        plan_conversions = request.form.get('plan_conversions')
        plan_bounce_rate = request.form.get('plan_bounce_rate')
        plan_time_on_site = request.form.get('plan_time_on_site')
        plan_page_depth = request.form.get('plan_page_depth')
        plan_robotness = request.form.get('plan_robotness')

        monitoring.plan_visits = int(plan_visits) if plan_visits else None
        monitoring.plan_conversions = int(plan_conversions) if plan_conversions else None
        monitoring.plan_bounce_rate = float(plan_bounce_rate) if plan_bounce_rate else None
        monitoring.plan_time_on_site = float(plan_time_on_site) if plan_time_on_site else None
        monitoring.plan_page_depth = float(plan_page_depth) if plan_page_depth else None
        monitoring.plan_robotness = float(plan_robotness) if plan_robotness else None

        # Traffic quality & Fraud monitoring
        plan_pi = request.form.get('plan_pi')
        plan_vtr = request.form.get('plan_vtr')
        logger.info(f"📝 EDIT - plan_vtr from form: '{plan_vtr}' (type: {type(plan_vtr).__name__})")
        plan_ivt = request.form.get('plan_ivt_impressions')
        plan_givt = request.form.get('plan_givt_impressions')
        plan_sivt = request.form.get('plan_sivt')
        plan_givt_clicks = request.form.get('plan_givt_clicks')

        monitoring.plan_pi = float(plan_pi) if plan_pi else None
        monitoring.plan_vtr = int(round(float(plan_vtr))) if plan_vtr else None
        logger.info(f"   → Saving plan_vtr: {monitoring.plan_vtr}")
        monitoring.plan_ivt_impressions = float(plan_ivt) if plan_ivt else None
        monitoring.plan_givt_impressions = float(plan_givt) if plan_givt else None
        monitoring.plan_sivt = float(plan_sivt) if plan_sivt else None
        monitoring.plan_givt_clicks = float(plan_givt_clicks) if plan_givt_clicks else None

        # IVT показатели (факт) - ручной ввод или Excel-выгрузка Adriver.
        # Выгрузка Adriver пишет эти поля напрямую через /upload_adriver_excel
        # (AJAX, без перезагрузки формы редактирования) - если после этого
        # основную форму сохранить раньше, чем её поля успеют подтянуть
        # свежие значения, пустая отправка затирала бы их в NULL. Поэтому
        # пустое значение теперь просто не трогает поле, а не обнуляет его -
        # очистить значение явно отсюда больше нельзя, только новой загрузкой/вводом.
        fact_ivt = request.form.get('fact_ivt_impressions')
        fact_givt = request.form.get('fact_givt_impressions')
        fact_sivt = request.form.get('fact_sivt_impressions')
        fact_givt_clicks = request.form.get('fact_givt_clicks')
        adriver_impressions = request.form.get('adriver_impressions')
        adriver_clicks = request.form.get('adriver_clicks')

        if fact_ivt:
            monitoring.fact_ivt_impressions = float(fact_ivt)
        if fact_givt:
            monitoring.fact_givt_impressions = float(fact_givt)
        if fact_sivt:
            monitoring.fact_sivt_impressions = float(fact_sivt)
        if fact_givt_clicks:
            monitoring.fact_givt_clicks = float(fact_givt_clicks)
        if adriver_impressions:
            monitoring.adriver_impressions = int(adriver_impressions)
        if adriver_clicks:
            monitoring.adriver_clicks = int(adriver_clicks)

        adriver_compare_date_from = request.form.get('adriver_compare_date_from', '').strip()
        monitoring.adriver_compare_date_from = datetime.strptime(adriver_compare_date_from, '%Y-%m-%d').date() if adriver_compare_date_from else None

        targetads_report_url = request.form.get('targetads_report_url', '').strip()
        monitoring.targetads_report_url = targetads_report_url if targetads_report_url else None

        # Manager
        manager = request.form.get('manager')
        monitoring.manager = manager if manager else None

        # Google Sheet URL
        google_sheet_url = request.form.get('google_sheet_url')
        monitoring.google_sheet_url = google_sheet_url if google_sheet_url else None

        # Asana task URL - only auto-pull the plan when the link is newly
        # added or changed to a different task. If it's unchanged, leave
        # plan_impressions/plan_clicks/etc as whatever was just submitted -
        # otherwise every save would re-overwrite manual corrections with
        # the Asana task's numbers.
        previous_asana_task_url = monitoring.asana_task_url
        asana_task_url = request.form.get('asana_task_url')
        monitoring.asana_task_url = asana_task_url if asana_task_url else None

        asana_warning = None
        if monitoring.asana_task_url and monitoring.asana_task_url != previous_asana_task_url:
            try:
                _sync_monitoring_from_asana(monitoring)
            except AsanaSyncError as e:
                asana_warning = str(e)

        db.session.commit()

        if asana_warning:
            flash(f'Мониторинг обновлен, но не удалось подтянуть план из Asana: {asana_warning}', 'error')
        else:
            flash('Мониторинг успешно обновлен', 'success')
        return redirect(url_for('monitoring'))

    except Exception as e:
        logger.error(f"Error updating monitoring: {e}")
        flash(f'Ошибка обновления мониторинга: {str(e)}', 'error')
        return redirect(url_for('monitoring'))


@app.route('/api/accounts/<int:account_id>/campaigns')
@login_required
def get_account_campaigns(account_id):
    """API endpoint to get campaigns for an account

    Query params:
        include_ids: comma-separated list of campaign IDs to include even if inactive
        client_id: filter to campaigns belonging to this client only
    """
    try:
        # Get active campaigns
        query = Campaign.query.filter_by(account_id=account_id, active=True)
        client_id = request.args.get('client_id', type=int)
        if client_id:
            query = query.filter_by(client_id=client_id)
        campaigns = query.all()

        # Get include_ids from query params
        include_ids_param = request.args.get('include_ids', '')
        if include_ids_param:
            try:
                include_ids = [int(x.strip()) for x in include_ids_param.split(',') if x.strip()]

                # Get campaigns with these IDs even if inactive
                if include_ids:
                    additional_campaigns = Campaign.query.filter(
                        Campaign.account_id == account_id,
                        Campaign.id.in_(include_ids),
                        Campaign.active == False
                    ).all()

                    # Add them to the list
                    campaigns.extend(additional_campaigns)
                    logger.info(f"Including {len(additional_campaigns)} inactive campaigns: {include_ids}")
            except ValueError as e:
                logger.warning(f"Invalid include_ids parameter: {include_ids_param}, error: {e}")

        # Remove duplicates and sort by campaign_id
        campaigns_dict = {c.id: c for c in campaigns}
        campaigns = sorted(campaigns_dict.values(), key=lambda x: x.campaign_id, reverse=True)

        return jsonify([{
            'id': c.id,
            'campaign_id': c.campaign_id,
            'name': c.name,
            'format_type': c.format_type,
            'active': c.active,
            'client_id': c.client_id,
            'client_name': c.client.name if c.client else None
        } for c in campaigns])
    except Exception as e:
        logging.error(f"Error loading campaigns for account {account_id}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/monitoring/<int:monitoring_id>')
@login_required
def get_monitoring_data(monitoring_id):
    """API endpoint to get monitoring data for editing"""
    try:
        monitoring = MonitoringCampaign.query.get_or_404(monitoring_id)

        return jsonify({
            'id': monitoring.id,
            'name': monitoring.name,
            'account_id': monitoring.account_id,
            'campaign_ids': monitoring.campaign_ids,
            'date_from': monitoring.date_from.strftime('%Y-%m-%d'),
            'date_to': monitoring.date_to.strftime('%Y-%m-%d'),
            'plan_impressions': monitoring.plan_impressions,
            'plan_clicks': monitoring.plan_clicks,
            'plan_visits': monitoring.plan_visits,
            'plan_conversions': monitoring.plan_conversions,
            'plan_bounce_rate': monitoring.plan_bounce_rate,
            'plan_time_on_site': monitoring.plan_time_on_site,
            'plan_page_depth': monitoring.plan_page_depth,
            'plan_robotness': monitoring.plan_robotness,
            'plan_pi': monitoring.plan_pi,
            'plan_vtr': monitoring.plan_vtr,
            'plan_ivt_impressions': monitoring.plan_ivt_impressions,
            'plan_givt_impressions': monitoring.plan_givt_impressions,
            'plan_sivt_impressions': monitoring.plan_sivt,  # Fix field name
            'plan_givt_clicks': monitoring.plan_givt_clicks,
            'fact_ivt_impressions': monitoring.fact_ivt_impressions,
            'fact_givt_impressions': monitoring.fact_givt_impressions,
            'fact_sivt_impressions': monitoring.fact_sivt_impressions,
            'fact_givt_clicks': monitoring.fact_givt_clicks,
            'adriver_impressions': monitoring.adriver_impressions,
            'adriver_clicks': monitoring.adriver_clicks,
            'adriver_compare_date_from': monitoring.adriver_compare_date_from.strftime('%Y-%m-%d') if monitoring.adriver_compare_date_from else None,
            'targetads_report_url': monitoring.targetads_report_url,
            'metrika_counter_id': monitoring.metrika_counter_id,
            'utm_source': monitoring.utm_source,
            'google_sheet_url': monitoring.google_sheet_url,
            'asana_task_url': monitoring.asana_task_url,
            'manager': monitoring.manager,
            'format_label': monitoring.get_format_label(),
            'verifier_links': [{
                'id': link.id,
                'verifier_type': link.verifier_type,
                'label': link.label,
                'permalink_url': link.permalink_url,
                'compare_date_from': link.compare_date_from.strftime('%Y-%m-%d') if link.compare_date_from else None,
                'ivt_impressions_percent': link.ivt_impressions_percent,
                'givt_impressions_percent': link.givt_impressions_percent,
                'sivt_impressions_percent': link.sivt_impressions_percent,
                'givt_clicks_percent': link.givt_clicks_percent,
                'mappings': [{
                    'id': mapping.id,
                    'sape_campaign_id': mapping.sape_campaign_id,
                    'sape_campaign_ids': mapping.campaign_ids_list(),
                    'insertion_name': mapping.insertion_name,
                    'verifier_impressions': mapping.verifier_impressions,
                    'verifier_clicks': mapping.verifier_clicks,
                    'sape_fact_impressions': mapping.sape_fact_impressions,
                    'sape_fact_clicks': mapping.sape_fact_clicks,
                } for mapping in link.mappings],
            } for link in monitoring.verifier_links]
        })
    except Exception as e:
        logger.error(f"Error getting monitoring data: {e}")
        return jsonify({'error': str(e)}), 500


def _refresh_verifier_campaign_facts(monitoring, client, date_from, date_to, only_link_id=None):
    """Fetch SAPE fact показы/клики for exactly the campaigns that have a
    Weborama verifier mapping, one API call per mapping (SAPE's
    multi-campaign stats call groups by date, not by campaign, so there's
    no way to get a per-mapping breakdown from a single combined call
    across ALL mappings at once - but a mapping covering several
    campaigns that share one verifier number can still be summed in one
    call, via SAPE's own campaignId "in" filter).

    Without this, the verifier discrepancy % would compare WCM's показы
    for one campaign against the whole monitoring's combined SAPE fact
    (all its campaigns) - wrong whenever a monitoring bundles more
    campaigns than the permalink actually covers. Scoped to only mapped
    campaigns, and only called from the existing refresh flows, so it
    adds at most a handful of extra requests, not one per monitoring.

    only_link_id restricts this to one link's own mappings - used when
    refreshing a single verifier card (so its SAPE side stays in sync
    with its own compare_date_from, not just the whole monitoring)."""
    mappings = [
        m for link in monitoring.verifier_links if link.verifier_type == 'weborama'
        and (only_link_id is None or link.id == only_link_id)
        for m in link.mappings if m.campaign_ids_list()
    ]
    if not mappings:
        return

    for mapping in mappings:
        campaigns = Campaign.query.filter(Campaign.id.in_(mapping.campaign_ids_list())).all()
        if not campaigns:
            continue
        # A pixel installed after the campaign's own start date would
        # otherwise compare a full-period SAPE fact against a
        # partial-period Weborama one - use the link's override if set
        # so both sides line up on the same window. date_from/date_to
        # here are datetimes (see callers), compare_date_from is a plain
        # date column - normalize before comparing/passing on.
        override = mapping.verifier_link.compare_date_from
        mapping_date_from = datetime.combine(override, datetime.min.time()) if override else date_from
        if mapping_date_from > date_to:
            continue
        try:
            stats = client.get_stats(
                campaign_ids=[int(c.campaign_id) for c in campaigns],
                date_from=mapping_date_from,
                date_to=date_to,
                fields=None
            )
            if not stats:
                continue
            total = stats.get('total', {})
            mapping.sape_fact_impressions = total.get('shows', 0)
            mapping.sape_fact_clicks = total.get('clicks', 0)
            mapping.sape_fact_updated_at = datetime.utcnow()
        except Exception as e:
            logger.error(f"⚠️ Failed to fetch SAPE fact for mapping {mapping.id} (campaigns {[c.campaign_id for c in campaigns]}): {e}")


def _refresh_adriver_fact(monitoring, client, date_to):
    """Same idea as _refresh_verifier_campaign_facts but for the single
    Adriver/Target Ads total on the monitoring itself - only runs when
    adriver_compare_date_from is set (the pixel went live after the
    campaign's own start date), fetching SAPE's fact scoped to that same
    shifted window so the discrepancy % isn't comparing a partial-period
    Adriver number against a full-period SAPE one."""
    if not monitoring.adriver_compare_date_from:
        return
    campaigns = monitoring.get_campaigns()
    if not campaigns:
        return
    date_from = datetime.combine(monitoring.adriver_compare_date_from, datetime.min.time())
    if date_from > date_to:
        return
    try:
        stats = client.get_stats(
            campaign_ids=[int(c.campaign_id) for c in campaigns],
            date_from=date_from,
            date_to=date_to,
            fields=None
        )
        if not stats:
            return
        total = stats.get('total', {})
        monitoring.adriver_fact_impressions = total.get('shows', 0)
        monitoring.adriver_fact_clicks = total.get('clicks', 0)
    except Exception as e:
        logger.error(f"⚠️ Failed to fetch scoped Adriver SAPE fact for monitoring {monitoring.id}: {e}")


class TargetAdsRefreshError(Exception):
    pass


def _refresh_targetads_fact(monitoring):
    """Pull показы/клики (+ IVT/GIVT/SIVT share) from TargetAds, scoped to
    the Sape (FS) source, for [adriver_compare_date_from or date_from .. yesterday].
    No-op if no targetads_report_url is set. Raises TargetAdsRefreshError
    on a real failure (bad link, auth, API error) so callers can decide
    whether to surface it or just log and move on."""
    if not monitoring.targetads_report_url:
        return None

    from app.api.targetads_client import TargetAdsClient, TargetAdsFetchError

    project_id = TargetAdsClient.extract_project_id(monitoring.targetads_report_url)
    if not project_id:
        raise TargetAdsRefreshError('Не удалось распознать project_id в ссылке TargetAds')

    yesterday = (datetime.now() - timedelta(days=1)).date()
    date_from = monitoring.adriver_compare_date_from or monitoring.date_from
    date_to = min(monitoring.date_to, yesterday)
    if date_from > date_to:
        raise TargetAdsRefreshError(f'Период ({date_from} — {date_to}) пуст - дата начала позже конца')

    try:
        client = TargetAdsClient()
        client.authenticate()
        result = client.get_daily_stats(
            project_id,
            datetime.combine(date_from, datetime.min.time()),
            datetime.combine(date_to, datetime.min.time())
        )
    except TargetAdsFetchError as e:
        raise TargetAdsRefreshError(str(e))

    monitoring.adriver_impressions = result['total_impressions']
    monitoring.adriver_clicks = result['total_clicks']
    if result.get('ivt_share') is not None:
        monitoring.fact_ivt_impressions = result['ivt_share']
    if result.get('givt_share') is not None:
        monitoring.fact_givt_impressions = result['givt_share']
    if result.get('sivt_share') is not None:
        monitoring.fact_sivt_impressions = result['sivt_share']

    logger.info(f"✅ Fetched TargetAds for monitoring {monitoring.id} ({date_from}..{date_to}): "
                f"{result['total_impressions']} показов, {result['total_clicks']} кликов, "
                f"IVT {result.get('ivt_share')}%")

    return {
        'date_from': str(date_from),
        'date_to': str(date_to),
        'impressions': result['total_impressions'],
        'clicks': result['total_clicks'],
        'ivt_share': result.get('ivt_share'),
        'givt_share': result.get('givt_share'),
        'sivt_share': result.get('sivt_share')
    }


@app.route('/monitoring/<int:monitoring_id>/refresh', methods=['POST'])
@login_required
def refresh_monitoring_data(monitoring_id):
    """Refresh actual data for monitoring from SAPE API"""
    try:
        monitoring = MonitoringCampaign.query.get_or_404(monitoring_id)

        # Get campaigns
        campaigns = monitoring.get_campaigns()
        if not campaigns:
            return jsonify({'success': False, 'error': 'No campaigns found'}), 400

        # Get account
        account = monitoring.account
        if not account or not account.api_token:
            return jsonify({'success': False, 'error': 'Account not configured'}), 400

        # Initialize SAPE client
        client = SapeAPIClient(login=account.login, token=account.api_token)

        if not client.authenticate():
            return jsonify({'success': False, 'error': 'SAPE authentication failed'}), 401

        # Get data from date_from to yesterday
        from datetime import timedelta
        yesterday = datetime.now() - timedelta(days=1)
        date_to = min(yesterday, datetime.combine(monitoring.date_to, datetime.min.time()))
        date_from = datetime.combine(monitoring.date_from, datetime.min.time())

        # Get campaign IDs
        campaign_ids = [int(c.campaign_id) for c in campaigns]

        # First, check what fields are available in SAPE API
        available_fields = client.get_available_stat_fields()
        if available_fields:
            logger.info(f"📋 Available statistic fields from SAPE API")

        # Request stats with extended fields
        # First, let's request without fields to see what's available
        stats = client.get_stats(
            campaign_ids=campaign_ids,
            date_from=date_from,
            date_to=date_to,
            fields=None  # Request all available fields
        )

        if not stats:
            return jsonify({'success': False, 'error': 'Failed to get stats from SAPE'}), 500

        # Extract totals and log available fields
        total = stats.get('total', {})
        logger.info(f"📊 SAPE API Response - Available fields in 'total': {list(total.keys())}")
        logger.info(f"📊 Full total data: {total}")

        # Also check if there are per-campaign statistics with more fields
        statistics = stats.get('statistics', [])
        if statistics and len(statistics) > 0:
            logger.info(f"📊 Sample statistics record fields: {list(statistics[0].keys())}")
            logger.info(f"📊 Sample statistics record: {statistics[0]}")

        # Update monitoring with actual data
        # SAPE API field names from web interface (traffic.sape.ru/reports)
        monitoring.fact_impressions = total.get('shows', 0)
        monitoring.fact_clicks = total.get('clicks', 0)
        monitoring.fact_visits = total.get('visits', 0)

        # Bounce rate (%) - already in percentage format from API
        monitoring.fact_bounce_rate = total.get('avgPostclickBounceRate', 0.0)

        # Time on site (in seconds)
        monitoring.fact_time_on_site = total.get('avgVisitDuration', 0.0)

        # Page depth
        monitoring.fact_page_depth = total.get('avgPostclickPageDepth', 0.0)

        # Robotness (%)
        monitoring.fact_robotness = total.get('avgPostclickRobot', 0.0)

        # VTR/VR (%) - use 'vtr' for video formats, 'vr' for banners/TGB
        # Check if any campaign is video format
        is_video = monitoring.is_video_format()
        if is_video:
            vtr_value = total.get('vtr', 0.0)
            monitoring.fact_vtr = int(round(vtr_value)) if vtr_value else None
            logger.info(f"📹 Video format detected, loaded VTR: {monitoring.fact_vtr}%")
        else:
            vr_value = total.get('vr', 0.0)
            monitoring.fact_vtr = int(round(vr_value)) if vr_value else None
            logger.info(f"🎯 Banner/TGB format detected, loaded VR: {monitoring.fact_vtr}%")

        _refresh_verifier_campaign_facts(monitoring, client, date_from, date_to)
        _refresh_adriver_fact(monitoring, client, date_to)

        # "Обновить сейчас" must refresh the verifier side too, not just the
        # SAPE fact - re-scrape every Weborama permalink on this monitoring
        # (one at a time, a broken/slow permalink shouldn't block the rest
        # or the SAPE numbers already refreshed above) and re-pull TargetAds
        # if a report link is set.
        weborama_links = VerifierLink.query.filter_by(monitoring_id=monitoring.id, verifier_type='weborama').all()
        for link in weborama_links:
            try:
                _fetch_and_apply_weborama_link(link)
            except WeboramaLinkFetchError as e:
                logger.error(f"⚠️ Weborama refresh failed for link {link.id} on monitoring {monitoring_id}: {e}")
            except Exception as e:
                logger.error(f"⚠️ Unexpected error refreshing Weborama link {link.id} on monitoring {monitoring_id}: {e}")

        if monitoring.targetads_report_url:
            try:
                _refresh_targetads_fact(monitoring)
            except TargetAdsRefreshError as e:
                logger.error(f"⚠️ TargetAds refresh failed for monitoring {monitoring_id}: {e}")
            except Exception as e:
                logger.error(f"⚠️ Unexpected error refreshing TargetAds for monitoring {monitoring_id}: {e}")

        monitoring.last_sync = datetime.utcnow()

        db.session.commit()

        logger.info(f"✅ Monitoring {monitoring_id} refreshed: {monitoring.fact_impressions:,} impressions, {monitoring.fact_clicks:,} clicks, {monitoring.fact_visits:,} visits")

        return jsonify({
            'success': True,
            'data': {
                'impressions': monitoring.fact_impressions,
                'clicks': monitoring.fact_clicks,
                'visits': monitoring.fact_visits,
                'bounce_rate': monitoring.fact_bounce_rate,
                'time_on_site': monitoring.fact_time_on_site,
                'page_depth': monitoring.fact_page_depth,
                'robotness': monitoring.fact_robotness,
                'vtr': monitoring.fact_vtr,
                'last_sync': monitoring.last_sync.strftime('%d.%m.%Y в %H:%M') if monitoring.last_sync else None
            }
        })

    except Exception as e:
        logger.error(f"Error refreshing monitoring data: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/monitoring/refresh_all', methods=['POST'])
@login_required
def refresh_all_monitorings():
    """Refresh actual data for all active monitorings from SAPE API"""
    try:
        # Get all active monitorings (not archived)
        monitorings = MonitoringCampaign.query.filter_by(archived=False).all()

        if not monitorings:
            return jsonify({'success': False, 'error': 'No active monitorings found'}), 404

        logger.info(f"🔄 Starting refresh for {len(monitorings)} active monitorings...")

        updated_count = 0
        failed_count = 0

        for monitoring in monitorings:
            try:
                logger.info(f"🔄 Refreshing monitoring {monitoring.id}: {monitoring.name}")

                # Get campaigns
                campaigns = monitoring.get_campaigns()
                if not campaigns:
                    logger.warning(f"⚠️ No campaigns found for monitoring {monitoring.id}")
                    failed_count += 1
                    continue

                # Get account
                account = monitoring.account
                if not account or not account.api_token:
                    logger.warning(f"⚠️ Account not configured for monitoring {monitoring.id}")
                    failed_count += 1
                    continue

                # Initialize SAPE client
                client = SapeAPIClient(login=account.login, token=account.api_token)

                if not client.authenticate():
                    logger.error(f"❌ SAPE authentication failed for monitoring {monitoring.id}")
                    failed_count += 1
                    continue

                # Get data from date_from to yesterday
                from datetime import timedelta
                yesterday = datetime.now() - timedelta(days=1)
                date_to = min(yesterday, datetime.combine(monitoring.date_to, datetime.min.time()))
                date_from = datetime.combine(monitoring.date_from, datetime.min.time())

                # Get campaign IDs
                campaign_ids = [int(c.campaign_id) for c in campaigns]

                # Request stats
                stats = client.get_stats(
                    campaign_ids=campaign_ids,
                    date_from=date_from,
                    date_to=date_to,
                    fields=None
                )

                if not stats:
                    logger.error(f"❌ Failed to get stats from SAPE for monitoring {monitoring.id}")
                    failed_count += 1
                    continue

                # Extract totals
                total = stats.get('total', {})

                # Update monitoring with actual data
                monitoring.fact_impressions = total.get('shows', 0)
                monitoring.fact_clicks = total.get('clicks', 0)
                monitoring.fact_visits = total.get('visits', 0)
                monitoring.fact_bounce_rate = total.get('avgPostclickBounceRate', 0.0)
                monitoring.fact_time_on_site = total.get('avgVisitDuration', 0.0)
                monitoring.fact_page_depth = total.get('avgPostclickPageDepth', 0.0)
                monitoring.fact_robotness = total.get('avgPostclickRobot', 0.0)

                # VTR/VR
                is_video = monitoring.is_video_format()
                if is_video:
                    vtr_value = total.get('vtr', 0.0)
                    monitoring.fact_vtr = int(round(vtr_value)) if vtr_value else None
                else:
                    vr_value = total.get('vr', 0.0)
                    monitoring.fact_vtr = int(round(vr_value)) if vr_value else None

                _refresh_verifier_campaign_facts(monitoring, client, date_from, date_to)
                _refresh_adriver_fact(monitoring, client, date_to)

                monitoring.last_sync = datetime.utcnow()

                db.session.commit()

                logger.info(f"✅ Monitoring {monitoring.id} refreshed: {monitoring.fact_impressions:,} impressions")
                updated_count += 1

                # Add delay between requests to avoid rate limiting
                import time
                time.sleep(2)

            except Exception as e:
                logger.error(f"❌ Error refreshing monitoring {monitoring.id}: {e}")
                failed_count += 1
                import traceback
                traceback.print_exc()
                continue

        logger.info(f"✅ Refresh completed: {updated_count} updated, {failed_count} failed")

        return jsonify({
            'success': True,
            'updated': updated_count,
            'failed': failed_count,
            'total': len(monitorings)
        })

    except Exception as e:
        logger.error(f"Error refreshing all monitorings: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/upload_adriver_excel/<int:monitoring_id>', methods=['POST'])
@login_required
def upload_adriver_excel(monitoring_id):
    """Upload and parse Adriver Excel file to update monitoring IVT data"""
    try:
        # Get monitoring
        monitoring = MonitoringCampaign.query.get_or_404(monitoring_id)

        # Check if file was uploaded
        if 'excel_file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400

        file = request.files['excel_file']

        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400

        # Check file extension
        if not file.filename.lower().endswith(('.xlsx', '.xls')):
            return jsonify({'success': False, 'error': 'Invalid file format. Please upload .xlsx or .xls file'}), 400

        # Save file temporarily
        import tempfile
        temp_dir = tempfile.mkdtemp()
        temp_file_path = os.path.join(temp_dir, file.filename)
        file.save(temp_file_path)

        logger.info(f"📤 Uploaded Adriver Excel for monitoring {monitoring_id}: {file.filename}")

        try:
            # Import parser
            from parse_adriver_excel import AdriverExcelParser

            # Parse Excel file
            parser = AdriverExcelParser(temp_file_path)
            ivt_data = parser.parse()

            if not ivt_data:
                return jsonify({'success': False, 'error': 'Failed to parse Excel file. Please ensure it contains IVT data.'}), 400

            # Update monitoring with IVT data
            monitoring.fact_ivt_impressions = ivt_data.get('ivt_impressions_percent', 0)
            monitoring.fact_givt_impressions = ivt_data.get('givt_impressions_percent', 0)
            monitoring.fact_sivt_impressions = ivt_data.get('sivt_impressions_percent', 0)
            monitoring.fact_givt_clicks = ivt_data.get('givt_clicks_percent', 0)
            monitoring.adriver_impressions = ivt_data.get('impressions')
            monitoring.adriver_clicks = ivt_data.get('clicks')

            # Update last sync time
            monitoring.last_sync = datetime.utcnow()

            db.session.commit()

            logger.info(f"✅ Updated monitoring {monitoring_id} with Adriver data:")
            logger.info(f"   Показы/клики: {monitoring.adriver_impressions}/{monitoring.adriver_clicks}")
            logger.info(f"   IVT показы: {monitoring.fact_ivt_impressions}%")
            logger.info(f"   GIVT показы: {monitoring.fact_givt_impressions}%")
            logger.info(f"   SIVT показы: {monitoring.fact_sivt_impressions}%")
            logger.info(f"   GIVT клики: {monitoring.fact_givt_clicks}%")

            return jsonify({
                'success': True,
                'data': {
                    'ivt_impressions': monitoring.fact_ivt_impressions,
                    'givt_impressions': monitoring.fact_givt_impressions,
                    'sivt_impressions': monitoring.fact_sivt_impressions,
                    'givt_clicks': monitoring.fact_givt_clicks,
                    'adriver_impressions': monitoring.adriver_impressions,
                    'adriver_clicks': monitoring.adriver_clicks,
                }
            })

        finally:
            # Clean up temp file
            try:
                import shutil
                shutil.rmtree(temp_dir)
            except:
                pass

    except Exception as e:
        logger.error(f"Error uploading Adriver Excel: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# VERIFIER LINKS (Weborama / Adriver permalinks per monitoring)
# ============================================================================

@app.route('/monitoring/<int:monitoring_id>/verifier-links/add', methods=['POST'])
@login_required
def add_verifier_link(monitoring_id):
    MonitoringCampaign.query.get_or_404(monitoring_id)
    data = request.get_json(silent=True) or {}

    verifier_type = data.get('verifier_type')
    if verifier_type not in ('weborama', 'adriver'):
        return jsonify({'success': False, 'error': 'Неизвестный тип верификатора'}), 400

    link = VerifierLink(
        monitoring_id=monitoring_id,
        verifier_type=verifier_type,
        label=(data.get('label') or '').strip() or None,
        permalink_url=(data.get('permalink_url') or '').strip() or None,
    )
    db.session.add(link)
    db.session.flush()

    # Every permalink starts with one mapping row to fill in - the "+"
    # button in the UI adds more when one permalink covers several
    # SAPE campaigns (e.g. a banner + a video insertion).
    if verifier_type == 'weborama':
        db.session.add(VerifierLinkMapping(verifier_link_id=link.id))

    db.session.commit()

    return jsonify({'success': True, 'id': link.id})


@app.route('/verifier-links/<int:link_id>/update', methods=['POST'])
@login_required
def update_verifier_link(link_id):
    link = VerifierLink.query.get_or_404(link_id)
    data = request.get_json(silent=True) or {}

    if 'label' in data:
        link.label = (data.get('label') or '').strip() or None
    if 'permalink_url' in data:
        link.permalink_url = (data.get('permalink_url') or '').strip() or None
    if 'compare_date_from' in data:
        value = (data.get('compare_date_from') or '').strip()
        link.compare_date_from = datetime.strptime(value, '%Y-%m-%d').date() if value else None
    for field in ('ivt_impressions_percent', 'givt_impressions_percent', 'sivt_impressions_percent', 'givt_clicks_percent'):
        if field in data:
            value = data.get(field)
            setattr(link, field, float(value) if value not in (None, '') else None)

    db.session.commit()
    return jsonify({'success': True})


@app.route('/verifier-links/<int:link_id>/delete', methods=['POST'])
@login_required
def delete_verifier_link(link_id):
    link = VerifierLink.query.get_or_404(link_id)
    db.session.delete(link)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/verifier-links/<int:link_id>/mappings/add', methods=['POST'])
@login_required
def add_verifier_mapping(link_id):
    VerifierLink.query.get_or_404(link_id)
    mapping = VerifierLinkMapping(verifier_link_id=link_id)
    db.session.add(mapping)
    db.session.commit()
    return jsonify({'success': True, 'id': mapping.id})




@app.route('/verifier-link-mappings/<int:mapping_id>/update', methods=['POST'])
@login_required
def update_verifier_mapping(mapping_id):
    mapping = VerifierLinkMapping.query.get_or_404(mapping_id)
    data = request.get_json(silent=True) or {}

    if 'sape_campaign_ids' in data:
        values = data.get('sape_campaign_ids') or []
        ids = [int(v) for v in values if v not in (None, '')]
        mapping.sape_campaign_ids = ids or None
        mapping.sape_campaign_id = ids[0] if ids else None
    elif 'sape_campaign_id' in data:
        value = data.get('sape_campaign_id')
        mapping.sape_campaign_id = int(value) if value not in (None, '') else None
        mapping.sape_campaign_ids = None
    if 'insertion_name' in data:
        mapping.insertion_name = (data.get('insertion_name') or '').strip() or None
    if 'verifier_impressions' in data:
        value = data.get('verifier_impressions')
        mapping.verifier_impressions = int(value) if value not in (None, '') else None
    if 'verifier_clicks' in data:
        value = data.get('verifier_clicks')
        mapping.verifier_clicks = int(value) if value not in (None, '') else None

    db.session.commit()
    return jsonify({'success': True})


@app.route('/verifier-link-mappings/<int:mapping_id>/delete', methods=['POST'])
@login_required
def delete_verifier_mapping(mapping_id):
    mapping = VerifierLinkMapping.query.get_or_404(mapping_id)
    db.session.delete(mapping)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/verifier-links/<int:link_id>/upload-excel', methods=['POST'])
@login_required
def upload_verifier_link_excel(link_id):
    """Upload an Adriver Excel export for one specific verifier link -
    stores the raw показы/клики (compared as-is against SAPE, not net of
    IVT) plus the IVT/GIVT/SIVT breakdown already parsed by
    AdriverExcelParser but previously discarded."""
    link = VerifierLink.query.get_or_404(link_id)

    if link.verifier_type != 'adriver':
        return jsonify({'success': False, 'error': 'Excel-загрузка доступна только для Adriver'}), 400

    if 'excel_file' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded'}), 400

    file = request.files['excel_file']
    if file.filename == '' or not file.filename.lower().endswith(('.xlsx', '.xls')):
        return jsonify({'success': False, 'error': 'Invalid file format. Please upload .xlsx or .xls file'}), 400

    import tempfile
    temp_dir = tempfile.mkdtemp()
    temp_file_path = os.path.join(temp_dir, file.filename)
    file.save(temp_file_path)

    try:
        from parse_adriver_excel import AdriverExcelParser
        parser = AdriverExcelParser(temp_file_path)
        ivt_data = parser.parse()

        if not ivt_data:
            return jsonify({'success': False, 'error': 'Failed to parse Excel file. Please ensure it contains IVT data.'}), 400

        link.verifier_impressions = ivt_data.get('impressions')
        link.verifier_clicks = ivt_data.get('clicks')
        link.ivt_impressions = ivt_data.get('ivt_impressions')
        link.ivt_impressions_percent = ivt_data.get('ivt_impressions_percent')
        link.givt_impressions = ivt_data.get('givt_impressions')
        link.givt_impressions_percent = ivt_data.get('givt_impressions_percent')
        link.sivt_impressions = ivt_data.get('sivt_impressions')
        link.sivt_impressions_percent = ivt_data.get('sivt_impressions_percent')
        link.ivt_clicks = ivt_data.get('ivt_clicks')
        link.ivt_clicks_percent = ivt_data.get('ivt_clicks_percent')
        link.givt_clicks = ivt_data.get('givt_clicks')
        link.givt_clicks_percent = ivt_data.get('givt_clicks_percent')
        link.sivt_clicks = ivt_data.get('sivt_clicks')
        link.sivt_clicks_percent = ivt_data.get('sivt_clicks_percent')
        link.last_fetched_at = datetime.utcnow()

        db.session.commit()

        logger.info(f"✅ Updated verifier link {link_id} from Adriver Excel: impressions={link.verifier_impressions}, clicks={link.verifier_clicks}")

        return jsonify({
            'success': True,
            'verifier_impressions': link.verifier_impressions,
            'verifier_clicks': link.verifier_clicks,
        })
    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


class WeboramaLinkFetchError(Exception):
    """Link-level failure (no permalink, page didn't load, period hasn't
    started yet) - as opposed to a single mapping not matching, which
    doesn't block the rest of the link's mappings."""
    pass


def _fetch_and_apply_weborama_link(link):
    """Fetches link.permalink_url ONCE and applies the result to every one
    of this link's mappings - a single Weborama page load already returns
    every Insertion row, so there's no need to hit the same permalink
    again per mapping (that would also be ~20s slower per extra mapping).

    Each mapping is matched independently: exact match on its own
    insertion_name if set, otherwise a one-time format guess (by the
    mapping's own SAPE campaign if picked, else the monitoring's format)
    that also records the matched name for next time. A mapping that
    can't be matched is recorded as failed in the returned dict but does
    NOT stop the other mappings from being updated.
    """
    if not link.permalink_url:
        raise WeboramaLinkFetchError('У пермалинка не указана ссылка')

    monitoring = link.monitoring
    yesterday = (datetime.now() - timedelta(days=1)).date()
    date_from = link.compare_date_from or monitoring.date_from
    date_to = min(monitoring.date_to, yesterday)

    if date_from > date_to:
        raise WeboramaLinkFetchError('Период мониторинга ещё не наступил')

    from app.api.weborama_client import fetch_insertions
    results = fetch_insertions(link.permalink_url, date_from, date_to)

    mapping_results = []
    for mapping in link.mappings:
        if mapping.insertion_name:
            matched = results.get(mapping.insertion_name)
            if not matched:
                mapping_results.append({
                    'id': mapping.id, 'success': False,
                    'error': f'Insertion "{mapping.insertion_name}" не найден. Доступны: {", ".join(results.keys())}',
                })
                continue
            mapping.verifier_impressions = matched['impressions']
            mapping.verifier_clicks = matched['clicks']
            mapping.insertion_name = matched['insertion_name']
            mapping.last_fetched_at = datetime.utcnow()
            mapping_results.append({
                'id': mapping.id, 'success': True,
                'insertion_name': matched['insertion_name'],
                'verifier_impressions': matched['impressions'],
                'verifier_clicks': matched['clicks'],
            })
        else:
            # No specific Insertion picked - this mapping wants the
            # permalink's combined total across every row it returned
            # (simpler than requiring an exact name match when there's
            # just one meaningful number, or the user doesn't need the
            # split). Stays blank afterward so future refreshes keep
            # summing everything rather than locking onto one row.
            total_impressions = sum(r['impressions'] for r in results.values())
            total_clicks = sum(r['clicks'] for r in results.values())
            mapping.verifier_impressions = total_impressions
            mapping.verifier_clicks = total_clicks
            mapping.last_fetched_at = datetime.utcnow()
            mapping_results.append({
                'id': mapping.id, 'success': True,
                'insertion_name': None,
                'verifier_impressions': total_impressions,
                'verifier_clicks': total_clicks,
            })

    link.last_fetched_at = datetime.utcnow()
    db.session.commit()

    return {
        'date_from': date_from.strftime('%Y-%m-%d'),
        'date_to': date_to.strftime('%Y-%m-%d'),
        'available_insertions': list(results.keys()),
        'mappings': mapping_results,
    }


@app.route('/verifier-links/<int:link_id>/fetch-weborama', methods=['POST'])
@login_required
def fetch_weborama_link(link_id):
    link = VerifierLink.query.get_or_404(link_id)

    if link.verifier_type != 'weborama':
        return jsonify({'success': False, 'error': 'Доступно только для Weborama'}), 400

    try:
        result = _fetch_and_apply_weborama_link(link)
    except WeboramaLinkFetchError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error fetching Weborama permalink for link {link_id}: {e}")
        return jsonify({'success': False, 'error': f'Ошибка получения данных из Weborama: {e}'}), 502

    logger.info(f"✅ Fetched verifier link {link_id} from Weborama ({result['date_from']}..{result['date_to']}): {result['mappings']}")

    # Keep the SAPE-fact side in sync too, scoped to this one link - its
    # compare_date_from (if set) drives both sides, so refreshing only the
    # Weborama half here would leave the discrepancy % comparing against a
    # stale SAPE fact from before the date was last changed.
    monitoring = link.monitoring
    account = monitoring.account
    if account and account.api_token:
        try:
            client = SapeAPIClient(login=account.login, token=account.api_token)
            if client.authenticate():
                yesterday = (datetime.now() - timedelta(days=1)).date()
                date_from = datetime.combine(monitoring.date_from, datetime.min.time())
                date_to = datetime.combine(min(monitoring.date_to, yesterday), datetime.min.time())
                _refresh_verifier_campaign_facts(monitoring, client, date_from, date_to, only_link_id=link.id)
                db.session.commit()
        except Exception as e:
            logger.error(f"⚠️ Failed to refresh SAPE fact alongside Weborama fetch for link {link_id}: {e}")

    return jsonify({'success': True, **result})


@app.route('/monitoring/<int:monitoring_id>/fetch-targetads', methods=['POST'])
@login_required
def fetch_targetads(monitoring_id):
    monitoring = MonitoringCampaign.query.get_or_404(monitoring_id)

    # Accept the link/date straight from the open form (not yet saved) so
    # "Обновить из TargetAds" works on a value the user just typed, the
    # same way the Weborama card saves itself right before fetching.
    body = request.get_json(silent=True) or {}
    report_url = (body.get('targetads_report_url') or monitoring.targetads_report_url or '').strip()
    if report_url:
        monitoring.targetads_report_url = report_url
    compare_date_from_str = (body.get('adriver_compare_date_from') or '').strip()
    if compare_date_from_str:
        monitoring.adriver_compare_date_from = datetime.strptime(compare_date_from_str, '%Y-%m-%d').date()

    if not monitoring.targetads_report_url:
        return jsonify({'success': False, 'error': 'Не указана ссылка на отчёт TargetAds'}), 400

    try:
        result = _refresh_targetads_fact(monitoring)
    except TargetAdsRefreshError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error fetching TargetAds for monitoring {monitoring_id}: {e}")
        return jsonify({'success': False, 'error': f'Ошибка получения данных из TargetAds: {e}'}), 502

    db.session.commit()

    return jsonify({'success': True, **result})


# ============================================================================
# REPORTS API ROUTES
# ============================================================================

@app.route('/api/clients/<int:account_id>')
def get_clients_by_account(account_id):
    """API endpoint to get clients for specific account"""
    clients = Client.query.filter_by(account_id=account_id, active=True).all()
    return jsonify([{
        'id': c.id,
        'client_id': c.client_id,
        'name': c.name
    } for c in clients])


@app.route('/api/campaigns/<int:account_id>')
def get_campaigns_by_account(account_id):
    """API endpoint to get campaigns for specific account"""
    client_id = request.args.get('client_id', type=int)

    query = Campaign.query.filter_by(account_id=account_id, active=True)

    # Filter by client if client_id is provided
    if client_id:
        query = query.filter_by(client_id=client_id)

    campaigns = query.all()

    return jsonify([{
        'id': c.id,
        'campaign_id': c.campaign_id,
        'name': c.name,
        'format_type': c.format_type or 'B',
        'client_id': c.client_id
    } for c in campaigns])


@app.route('/api/worksheets', methods=['POST'])
def get_worksheets():
    """API endpoint to get list of worksheets from Google Sheets"""
    try:
        data = request.get_json()
        google_sheet_url = data.get('google_sheet_url')

        if not google_sheet_url:
            return jsonify({'error': 'Google Sheet URL is required'}), 400

        # Get worksheets using GoogleSheetsClient
        worksheets = GoogleSheetsClient.get_worksheet_names(google_sheet_url)

        if worksheets is None:
            return jsonify({'error': 'Не удалось подключиться к Google Sheets'}), 400

        return jsonify({'worksheets': worksheets})
    except Exception as e:
        print(f"Error getting worksheets: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/reports/<int:report_id>')
def get_report_data(report_id):
    """API endpoint to get report data for editing"""
    try:
        report = ReportConfig.query.get_or_404(report_id)
        monitoring = MonitoringCampaign.query.filter_by(report_config_id=report.id).first()

        return jsonify({
            'id': report.id,
            'name': report.name,
            'account_id': report.campaign.account_id,
            'campaign_ids': report.campaign_ids,
            'campaign_settings': report.campaign_settings or {},
            'manager': report.manager,
            'brand': report.brand,
            'campaign_mode': report.campaign_mode,
            'google_sheet_url': report.google_sheet_url,
            'worksheet_name': report.worksheet_name,
            'schedule_days': report.schedule_days,
            'schedule_time': report.schedule_time,
            'schedule_enabled': report.schedule_enabled,
            'asana_task_url': monitoring.asana_task_url if monitoring else None,
        })
    except Exception as e:
        logger.error(f"Error getting report data: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/sync-status')
def sync_status():
    """Get last sync timestamp (no auth required)"""
    import os
    from datetime import datetime

    sync_file = '.last_sync'
    if os.path.exists(sync_file):
        with open(sync_file, 'r') as f:
            timestamp_str = f.read().strip()
            try:
                timestamp = datetime.fromisoformat(timestamp_str)
                return jsonify({
                    'synced': True,
                    'timestamp': timestamp.isoformat(),
                    'formatted': timestamp.strftime('%d.%m.%Y %H:%M')
                })
            except:
                pass

    return jsonify({'synced': False})


@app.route('/api/reports/update-by-sheet', methods=['POST'])
def update_by_sheet():
    """
    API endpoint для обновления отчёта из Google Sheets
    Принимает: { "sheet_url": "...", "sheet_name": "..." }
    """
    try:
        data = request.get_json()
        sheet_url = data.get('sheet_url')
        sheet_name = data.get('sheet_name')

        if not sheet_url:
            return jsonify({'error': 'Не указан sheet_url'}), 400

        # Нормализация URL (удаляем параметры и якори)
        sheet_url = sheet_url.split('#')[0].split('?')[0]

        # Поиск отчёта по URL таблицы
        report = ReportConfig.query.filter_by(google_sheet_url=sheet_url).first()

        if not report:
            return jsonify({
                'error': f'Отчёт для таблицы не найден.\n\nСоздайте отчёт через меню:\n📈 SAPE Reports → 📊 Создать новый отчёт'
            }), 404

        # Если указан конкретный лист, проверяем совпадение
        if sheet_name and report.worksheet_name and report.worksheet_name != sheet_name:
            return jsonify({
                'error': f'Этот отчёт настроен для листа "{report.worksheet_name}", а не "{sheet_name}"'
            }), 400

        # Запускаем обновление отчёта
        success = run_report(report.id)

        if success:
            return jsonify({
                'success': True,
                'message': f'✅ Отчёт "{report.name}" успешно обновлён!',
                'report_id': report.id,
                'report_name': report.name
            })
        else:
            return jsonify({
                'error': 'Ошибка при обновлении отчёта. Проверьте логи панели.'
            }), 500

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in update_by_sheet API: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/reports/add', methods=['GET', 'POST'])
def add_report():
    """Add new report configuration"""
    if request.method == 'POST':
        # Get form data
        report_name = request.form.get('report_name', '').strip() or None
        manager = request.form.get('manager', '').strip() or None
        campaign_ids_str = request.form.getlist('campaign_ids')  # List of campaign IDs
        campaign_mode = request.form.get('campaign_mode', 'separate')
        google_sheet_url = request.form.get('google_sheet_url')
        worksheet_name = request.form.get('worksheet_name', '').strip() or None
        asana_task_url = request.form.get('asana_task_url', '').strip() or None

        # Schedule
        schedule_days = request.form.get('schedule_days')
        schedule_time = request.form.get('schedule_time')

        if not campaign_ids_str:
            flash('Выберите хотя бы одну кампанию', 'error')
            accounts = SapeAccount.query.filter_by(active=True).all()
            return render_template('add_report.html', accounts=accounts)

        # Convert to integers
        campaign_ids = [int(cid) for cid in campaign_ids_str]

        # Get campaign settings (frequencies, variances) and formats for each campaign
        campaign_settings = {}
        campaign_frequencies = {}  # Keep for backward compatibility

        for cid in campaign_ids:
            # Get new frequency settings (4 fields per campaign)
            daily_freq = request.form.get(f'daily_freq_{cid}', '3.0')
            daily_var = request.form.get(f'daily_var_{cid}', '0.1')
            total_freq = request.form.get(f'total_freq_{cid}', '3.0')
            total_var = request.form.get(f'total_var_{cid}', '0.1')

            try:
                daily_frequency = float(daily_freq)
                daily_variance = float(daily_var)
                total_frequency = float(total_freq)
                total_variance = float(total_var)

                # No validation - daily and total frequencies are independent parameters
                # User can set total_frequency higher or lower than daily_frequency

                campaign_settings[str(cid)] = {
                    'daily_frequency': daily_frequency,
                    'daily_variance': daily_variance,
                    'total_frequency': total_frequency,
                    'total_variance': total_variance
                }

                # Backward compatibility: save to old format too
                campaign_frequencies[str(cid)] = daily_frequency

            except ValueError:
                # Default values if parsing fails
                campaign_settings[str(cid)] = {
                    'daily_frequency': 3.0,
                    'daily_variance': 0.1,
                    'total_frequency': 3.0,
                    'total_variance': 0.1
                }
                campaign_frequencies[str(cid)] = 3.0

            # Update format if changed
            format_key = f'format_{cid}'
            format_value = request.form.get(format_key)
            if format_value:
                campaign = Campaign.query.get(cid)
                if campaign:
                    campaign.format_type = format_value

        # Commit format changes
        db.session.commit()

        # Get campaigns
        campaigns = Campaign.query.filter(Campaign.id.in_(campaign_ids)).all()
        if not campaigns:
            flash('Кампании не найдены', 'error')
            accounts = SapeAccount.query.filter_by(active=True).all()
            return render_template('add_report.html', accounts=accounts)

        # NOTE: Structure validation moved to run_report
        # We no longer validate structure at creation time to allow flexible setup
        # Structure will be auto-detected when report is executed

        # Create report config WITHOUT structure validation
        first_campaign = campaigns[0]

        report = ReportConfig(
            name=report_name,  # Custom report name (optional)
            campaign_id=first_campaign.id,  # Primary campaign for display
            campaign_ids=campaign_ids,  # All selected campaigns
            campaign_mode=campaign_mode,
            google_sheet_url=google_sheet_url,
            worksheet_name=worksheet_name,  # Selected worksheet name
            data_start_row=None,  # Will be detected at runtime
            date_column=None,
            impressions_column=None,
            reach_column=None,
            clicks_column=None,
            ctr_column=None,
            completes_column=None,
            spent_column=None,
            campaign_settings=campaign_settings,  # NEW: Campaign settings with daily/total frequencies
            campaign_frequencies=campaign_frequencies,  # DEPRECATED: Kept for backward compatibility
            frequency_variance=0.1,  # DEPRECATED: Default value for backward compatibility
            schedule_days=schedule_days,
            schedule_time=schedule_time,
            schedule_enabled=request.form.get('schedule_enabled') == '1',
            manager=manager
        )

        db.session.add(report)
        db.session.commit()

        # Automatically create monitoring for this report
        try:
            # Get account_id from first campaign
            account_id = first_campaign.account_id

            # Set monitoring name (use report name or campaign name)
            monitoring_name = report_name if report_name else f"Мониторинг: {first_campaign.name}"

            # Set dates: use today as start, +30 days as default end
            from datetime import timedelta
            today = datetime.now().date()
            default_end_date = today + timedelta(days=30)

            # Create monitoring
            monitoring = MonitoringCampaign(
                name=monitoring_name,
                report_config_id=report.id,
                account_id=account_id,
                campaign_ids=campaign_ids,
                date_from=today,
                date_to=default_end_date,
                manager=manager,
                google_sheet_url=google_sheet_url,
                asana_task_url=asana_task_url
            )

            db.session.add(monitoring)
            db.session.commit()

            logging.info(f"✅ Auto-created monitoring {monitoring.id} for report {report.id}")

            # If an Asana task was linked, pull its plan straight away -
            # using the task's own "дата старта"/"дата завершения" fields
            # as the monitoring's period (instead of the today+30d
            # default) when the task actually has them set.
            if asana_task_url:
                try:
                    from app.api.asana_client import AsanaClient
                    client = AsanaClient()
                    task_gid = client.extract_task_gid(asana_task_url)
                    if task_gid:
                        task = client.get_task(task_gid)
                        monitoring_campaigns = monitoring.get_campaigns()
                        format_type = monitoring_campaigns[0].format_type if monitoring_campaigns else None
                        format_idx = AsanaClient.format_index_for_campaign_type(format_type)
                        parsed = client.parse_monitoring_fields(task, format_idx=format_idx)
                        if parsed.get('task_date_from') and parsed.get('task_date_to'):
                            monitoring.date_from = parsed['task_date_from']
                            monitoring.date_to = parsed['task_date_to']
                            db.session.commit()

                        asana_result = _sync_monitoring_from_asana(monitoring)
                        db.session.commit()
                        logging.info(f"✅ Synced auto-created monitoring {monitoring.id} from Asana: {asana_result['updated_fields']}")
                    else:
                        logging.warning(f"⚠️ Could not extract Asana task GID from {asana_task_url}")
                except AsanaSyncError as e:
                    logging.warning(f"⚠️ Asana sync failed for auto-created monitoring {monitoring.id}: {e}")
                except Exception as e:
                    db.session.rollback()
                    logging.error(f"⚠️ Unexpected error syncing Asana for auto-created monitoring {monitoring.id}: {e}")
        except Exception as e:
            # Don't fail report creation if monitoring creation fails
            logging.error(f"⚠️ Failed to auto-create monitoring: {e}")
            # Rollback monitoring creation but keep report
            db.session.rollback()

        # Try to extract brand from sheet (if sheet exists and has data)
        try:
            print(f"🏷️ Attempting to extract brand from sheet for new report...")
            gs_client = GoogleSheetsClient(
                credentials_file=app.config['GOOGLE_CREDENTIALS_FILE'],
                scopes=app.config['GOOGLE_SCOPES']
            )

            if gs_client.authenticate():
                brand_name = gs_client.extract_brand_from_sheet(
                    sheet_url=google_sheet_url,
                    sheet_name=worksheet_name,
                    cached_worksheet=None
                )

                if brand_name:
                    report.brand = brand_name
                    db.session.commit()
                    print(f"✅ Brand extracted and saved: '{brand_name}'")
                else:
                    print(f"⚠️ Brand not found in sheet (will try again on first update)")
            else:
                print(f"⚠️ Could not authenticate with Google Sheets")
        except Exception as e:
            # Don't fail report creation if brand extraction fails
            print(f"⚠️ Brand extraction failed (will try on first update): {e}")

        campaign_names = ', '.join([c.name for c in campaigns])
        mode_labels = {'separate': 'Раздельно', 'total': 'Едино', 'by_creative': 'По креативам'}
        flash(f'Отчет успешно создан для кампаний: {campaign_names}. Режим: {mode_labels.get(campaign_mode, campaign_mode)}', 'success')
        return redirect(url_for('reports'))

    # Get all accounts for dropdown
    accounts = SapeAccount.query.filter_by(active=True).all()
    return render_template('add_report.html', accounts=accounts)


@app.route('/reports/<int:report_id>/run')
def run_report(report_id):
    """Show progress page for report generation"""
    report = ReportConfig.query.get_or_404(report_id)
    return render_template('report_run_progress.html', report=report)


@app.route('/reports/<int:report_id>/run/execute')
def execute_run_report(report_id):
    """Execute report generation and return progress as JSON"""
    from flask import Response
    import json
    from datetime import datetime as dt, timedelta

    def generate():
        with app.app_context():
            try:
                report = ReportConfig.query.get_or_404(report_id)

                yield f"data: {json.dumps({'type': 'status', 'message': 'Подготовка к формированию отчета...'})}\n\n"

                # Get all campaigns for this report
                campaigns = Campaign.query.filter(Campaign.id.in_(report.campaign_ids)).all()
                if not campaigns:
                    yield f"data: {json.dumps({'type': 'complete', 'success': False, 'error': 'Не найдены кампании для отчета'})}\n\n"
                    return

                # Get account from first campaign
                account = campaigns[0].account

                yield f"data: {json.dumps({'type': 'status', 'message': 'Подключение к SAPE API...'})}\n\n"

                # Initialize SAPE client
                sape_client = SapeAPIClient(login=account.login, token=account.api_token)
                if not sape_client.authenticate():
                    yield f"data: {json.dumps({'type': 'complete', 'success': False, 'error': 'Ошибка авторизации в SAPE'})}\n\n"
                    return

                # Get date range from request or use last 7 days
                date_from_str = request.args.get('date_from')
                date_to_str = request.args.get('date_to')

                if date_from_str and date_to_str:
                    date_from = dt.strptime(date_from_str, '%Y-%m-%d')
                    date_to = dt.strptime(date_to_str, '%Y-%m-%d')
                else:
                    date_to = datetime.now()
                    date_from = date_to - timedelta(days=7)

                period_str = f"{date_from.strftime('%d.%m.%Y')} - {date_to.strftime('%d.%m.%Y')}"

                yield f"data: {json.dumps({'type': 'status', 'message': f'Получение данных за период {period_str}...'})}\n\n"

                # Initialize Google Sheets client
                gs_client = GoogleSheetsClient(
                    credentials_file=app.config['GOOGLE_CREDENTIALS_FILE'],
                    scopes=app.config['GOOGLE_SCOPES']
                )

                yield f"data: {json.dumps({'type': 'status', 'message': 'Обработка данных кампаний...'})}\n\n"

                # Call the old processing logic (imported from run_report_old)
                # For now, we'll use a simplified version and redirect to old route
                # This is because the full implementation is very complex

                # Build URL for old route
                old_url = url_for('run_report_old', report_id=report_id, date_from=date_from.strftime('%Y-%m-%d'), date_to=date_to.strftime('%Y-%m-%d'), _external=True)

                yield f"data: {json.dumps({'type': 'complete', 'success': False, 'error': 'Функция в разработке. Перенаправление на старую версию...', 'redirect': old_url})}\n\n"

            except Exception as e:
                logging.error(f"Error in execute_run_report: {e}", exc_info=True)
                yield f"data: {json.dumps({'type': 'complete', 'success': False, 'error': str(e)})}\n\n"

    return Response(generate(), mimetype='text/event-stream')


def _build_ad_scoped_daily_data(ad_stats, matched_ad_ids):
    """Sum per-creative daily SAPE stats (from get_daily_stats_by_ad) across
    just matched_ad_ids, into the same [{date, date_iso, impressions,
    clicks, ctr}] shape write_daily_data() expects."""
    daily_by_ad = ad_stats.get('daily_by_ad', {})
    totals_by_date = {}
    for ad_id in matched_ad_ids:
        for date_iso, vals in daily_by_ad.get(ad_id, {}).items():
            entry = totals_by_date.setdefault(date_iso, {'impressions': 0, 'clicks': 0})
            entry['impressions'] += vals['impressions']
            entry['clicks'] += vals['clicks']

    result = []
    for date_iso in sorted(totals_by_date.keys()):
        imp = totals_by_date[date_iso]['impressions']
        clk = totals_by_date[date_iso]['clicks']
        date_obj = datetime.strptime(date_iso, '%Y-%m-%d')
        result.append({
            'date': date_obj.strftime('%d.%m.%Y'),
            'date_iso': date_iso,
            'impressions': imp,
            'clicks': clk,
            'ctr': round(clk / imp * 100, 2) if imp > 0 else 0.0
        })
    return result


@app.route('/reports/<int:report_id>/run-old')
def run_report_old(report_id):
    """Run report manually (old synchronous version)"""
    report = ReportConfig.query.get_or_404(report_id)

    # Get all campaigns for this report
    campaigns = Campaign.query.filter(Campaign.id.in_(report.campaign_ids)).all()
    if not campaigns:
        flash('Не найдены кампании для отчета', 'error')
        return redirect(url_for('reports'))

    # Get account from first campaign (all campaigns should be from same account)
    account = campaigns[0].account

    try:
        # Initialize SAPE client with login and token
        sape_client = SapeAPIClient(login=account.login, token=account.api_token)

        # Authenticate
        if not sape_client.authenticate():
            raise Exception("SAPE authentication failed")

        # Get date range from request or use last 7 days
        date_from_str = request.args.get('date_from')
        date_to_str = request.args.get('date_to')

        if date_from_str and date_to_str:
            from datetime import datetime as dt
            date_from = dt.strptime(date_from_str, '%Y-%m-%d')
            date_to = dt.strptime(date_to_str, '%Y-%m-%d')
        else:
            # Default to last 7 days
            from datetime import timedelta
            date_to = datetime.now()
            date_from = date_to - timedelta(days=7)

        # Initialize Google Sheets client
        gs_client = GoogleSheetsClient(
            credentials_file=app.config['GOOGLE_CREDENTIALS_FILE'],
            scopes=app.config['GOOGLE_SCOPES']
        )

        # ==================== REALWEB CUSTOM VIDEO DETAILED REPORT ====================
        # Check if this is Realweb custom report (by report name)
        is_realweb_report = 'realweb' in report.name.lower() if report.name else False

        if is_realweb_report:
            print(f"\n{'='*60}")
            print(f"🎬 REALWEB VIDEO DETAILED REPORT MODE")
            print(f"   Campaigns: {len(campaigns)}")
            print(f"   Period: {date_from.strftime('%Y-%m-%d')} to {date_to.strftime('%Y-%m-%d')}")
            print(f"{'='*60}\n")

            campaigns_daily_data = []
            daily_variances = []  # Collect variances to calculate average

            for campaign in campaigns:
                print(f"📊 Processing campaign {campaign.campaign_id} ({campaign.name})")

                # Get daily stats with video metrics
                daily_data = sape_client.get_daily_stats(
                    campaign_ids=[int(campaign.campaign_id)],
                    date_from=date_from,
                    date_to=date_to,
                    include_video_metrics=True  # Always include video metrics for Realweb
                )

                if not daily_data:
                    print(f"⚠️  No data for campaign {campaign.campaign_id} ({campaign.name})")
                    continue

                # DEBUG: Print first day data to see video metrics
                if len(daily_data) > 0:
                    print(f"   🔍 DEBUG First day data: {daily_data[0]}")

                # Get frequency and variance for this campaign
                frequency = 3.0  # Default
                daily_variance = 0.1  # Default

                cid_str = str(campaign.id)
                # Try new format first (campaign_settings)
                if report.campaign_settings and cid_str in report.campaign_settings:
                    settings = report.campaign_settings[cid_str]
                    frequency = settings.get('daily_frequency', 3.0)
                    daily_variance = settings.get('daily_variance', 0.1)
                # Fallback to old format
                elif report.campaign_frequencies and cid_str in report.campaign_frequencies:
                    frequency = report.campaign_frequencies[cid_str]
                    daily_variance = report.frequency_variance or 0.1

                daily_variances.append(daily_variance)

                campaigns_daily_data.append({
                    'campaign_id': campaign.campaign_id,
                    'campaign_name': campaign.name,
                    'format_type': campaign.format_type,  # Add format type (B/V/CTV/TGB)
                    'frequency': frequency,
                    'daily_data': daily_data
                })

                print(f"   ✅ Got {len(daily_data)} days of data (frequency: {frequency}, variance: {daily_variance})")

            if not campaigns_daily_data:
                raise Exception("No data for any campaign in the period")

            # Calculate average variance
            avg_daily_variance = sum(daily_variances) / len(daily_variances) if daily_variances else 0.1

            # Write video detailed report to Google Sheets
            success = gs_client.write_video_detailed_data(
                sheet_url=report.google_sheet_url,
                sheet_name=report.worksheet_name,
                campaigns_daily_data=campaigns_daily_data,
                frequency_variance=avg_daily_variance
            )

            if not success:
                raise Exception("Failed to write Realweb video detailed report to Google Sheets")

            # Calculate metrics for logging
            total_rows = sum(len(c['daily_data']) for c in campaigns_daily_data)
            total_impressions = sum(
                sum(d['impressions'] for d in c['daily_data'])
                for c in campaigns_daily_data
            )
            total_clicks = sum(
                sum(d['clicks'] for d in c['daily_data'])
                for c in campaigns_daily_data
            )

            # Log success
            avg_ctr = round(total_clicks / total_impressions * 100, 2) if total_impressions > 0 else 0
            metrics = {
                'total_impressions': total_impressions,
                'total_clicks': total_clicks,
                'avg_ctr': avg_ctr,
                'total_rows': total_rows,
                'campaigns_updated': len(campaigns_daily_data)
            }

            log = ReportLog(
                report_config_id=report.id,
                status='success',
                metrics=metrics
            )
            db.session.add(log)

            report.last_update = datetime.utcnow()
            db.session.commit()

            flash(f'Realweb отчёт успешно обновлен! Записано {total_rows} строк для {len(campaigns_daily_data)} кампаний. Всего показов: {total_impressions:,}, кликов: {total_clicks:,}', 'success')
            return redirect(url_for('reports'))

        # ==================== TOTAL REPORT MODE ====================
        if report.campaign_mode == 'total':
            print(f"\n{'='*60}")
            print(f"📊 TOTAL REPORT MODE: Processing {len(campaigns)} campaigns")
            print(f"   Period: {date_from.strftime('%Y-%m-%d')} to {date_to.strftime('%Y-%m-%d')}")
            print(f"{'='*60}\n")

            campaigns_data = []
            total_impressions = 0
            total_clicks = 0
            total_variances = []  # Collect variances to calculate average

            for campaign in campaigns:
                # Get data for this campaign for entire period
                daily_data = sape_client.get_daily_stats(
                    campaign_ids=[int(campaign.campaign_id)],
                    date_from=date_from,
                    date_to=date_to,
                    include_video_metrics=(campaign.format_type in ['V', 'CTV'])
                )

                if not daily_data:
                    print(f"⚠️  No data for campaign {campaign.campaign_id} ({campaign.name})")
                    continue

                # Sum all data for the period
                period_shows = sum(d['impressions'] for d in daily_data)
                period_clicks = sum(d['clicks'] for d in daily_data)

                # Get frequency and variance for this campaign
                frequency = 3.0  # Default
                total_variance = 0.1  # Default

                cid_str = str(campaign.id)
                # Try new format first (campaign_settings)
                if report.campaign_settings and cid_str in report.campaign_settings:
                    settings = report.campaign_settings[cid_str]
                    frequency = settings.get('total_frequency', 3.0)
                    total_variance = settings.get('total_variance', 0.1)
                # Fallback to old format
                elif report.campaign_frequencies and cid_str in report.campaign_frequencies:
                    frequency = report.campaign_frequencies[cid_str]
                    total_variance = report.frequency_variance or 0.1

                total_variances.append(total_variance)

                # Calculate AVERAGE reach across days (not sum!)
                # Apply variance ONCE per campaign (not per day!)
                # For total reports: frequency must be below target value
                import random
                min_freq = max(frequency - total_variance, 0.1)
                max_freq = frequency - 0.01  # Must be strictly less than target
                actual_frequency = random.uniform(min_freq, max_freq)

                # Now calculate reach for each day using this frequency
                daily_reaches = []
                for day_data in daily_data:
                    day_shows = day_data['impressions']
                    if day_shows > 0:
                        day_reach = int(day_shows / actual_frequency)
                        daily_reaches.append(day_reach)

                # Average reach across all days
                average_reach = int(sum(daily_reaches) / len(daily_reaches)) if daily_reaches else 0

                # For total report: calculate PERIOD reach (not average daily)
                # Period reach = total shows for period / frequency
                period_reach = int(period_shows / actual_frequency) if actual_frequency > 0 else 0

                print(f"✅ Campaign {campaign.campaign_id} ({campaign.name}):")
                print(f"   Shows: {period_shows:,}, Clicks: {period_clicks:,}")
                print(f"   Frequency target: {frequency} ± {total_variance}, actual: {actual_frequency:.2f}")
                print(f"   Average daily reach: {average_reach:,} (from {len(daily_reaches)} days)")
                print(f"   Period reach: {period_reach:,} (shows / frequency)")

                campaigns_data.append({
                    'campaign_id': campaign.campaign_id,
                    'shows': period_shows,
                    'clicks': period_clicks,
                    'frequency': frequency,
                    'period_reach': period_reach  # Use period reach for total reports
                })

                total_impressions += period_shows
                total_clicks += period_clicks

            if not campaigns_data:
                raise Exception("No data for any campaign in the period")

            # Calculate average variance
            avg_total_variance = sum(total_variances) / len(total_variances) if total_variances else 0.1

            # Write total report to Google Sheets
            success = gs_client.write_total_report_data(
                sheet_url=report.google_sheet_url,
                sheet_name=report.worksheet_name,
                campaigns_data=campaigns_data,
                frequency_variance=avg_total_variance
            )

            if not success:
                raise Exception("Failed to write total report to Google Sheets")

            # Log success
            avg_ctr = round(total_clicks / total_impressions * 100, 2) if total_impressions > 0 else 0
            metrics = {
                'total_impressions': total_impressions,
                'total_clicks': total_clicks,
                'avg_ctr': avg_ctr,
                'campaigns_updated': len(campaigns_data)
            }

            log = ReportLog(
                report_config_id=report.id,
                status='success',
                metrics=metrics
            )
            db.session.add(log)

            report.last_update = datetime.utcnow()
            db.session.commit()

            flash(f'Сводный отчёт успешно обновлен для {len(campaigns_data)} кампаний. Всего показов: {total_impressions:,}, кликов: {total_clicks:,}', 'success')
            return redirect(url_for('reports'))

        # ==================== BY-CREATIVE REPORT MODE ====================
        # One campaign can have several sections in the sheet, each scoped to
        # a subset of its creatives (e.g. "Показатели кампании крео 1 <adIds>" /
        # "...крео 2 <adIds>") - the adIds literally in the header text tell us
        # which creatives belong to which section. No manual ID/name field
        # needed in the report form: we fetch the campaign's real adId list
        # from SAPE and match it against numbers found in the sheet headers.
        if report.campaign_mode == 'by_creative':
            print(f"\n{'='*60}")
            print(f"🎨 BY-CREATIVE REPORT MODE: Processing {len(campaigns)} campaigns")
            print(f"   Period: {date_from.strftime('%Y-%m-%d')} to {date_to.strftime('%Y-%m-%d')}")
            print(f"{'='*60}\n")

            cached_worksheet_object = gs_client.get_worksheet_object(
                sheet_url=report.google_sheet_url,
                sheet_name=report.worksheet_name
            )
            cached_worksheet_data = cached_worksheet_object.get('A1:DZ300') if cached_worksheet_object else None

            total_impressions = 0
            total_clicks = 0
            sections_written = 0

            for campaign in campaigns:
                print(f"\n🔍 Fetching per-creative stats for campaign {campaign.campaign_id} ({campaign.name})")
                ad_stats = sape_client.get_daily_stats_by_ad(
                    campaign_ids=[int(campaign.campaign_id)],
                    date_from=date_from,
                    date_to=date_to
                )
                known_ad_ids = set(ad_stats.get('daily_by_ad', {}).keys())
                print(f"   Found {len(known_ad_ids)} creatives with data: {sorted(ad_stats.get('ad_names', {}).values())}")

                all_structures = gs_client.auto_detect_all_structures(
                    sheet_url=report.google_sheet_url,
                    sheet_name=report.worksheet_name,
                    campaign_id=str(campaign.campaign_id),
                    cached_data=cached_worksheet_data,
                    known_ad_ids=known_ad_ids
                )

                if not all_structures:
                    print(f"❌ No sections found in sheet for campaign {campaign.campaign_id}")
                    continue

                cid_str = str(campaign.id)
                if report.campaign_settings and cid_str in report.campaign_settings:
                    settings = report.campaign_settings[cid_str]
                    daily_frequency = settings.get('daily_frequency', 3.0)
                    daily_variance = settings.get('daily_variance', 0.1)
                    total_frequency = settings.get('total_frequency', 3.0)
                    total_variance = settings.get('total_variance', 0.1)
                else:
                    daily_frequency, daily_variance, total_frequency, total_variance = 3.0, 0.1, 3.0, 0.1

                for structure in all_structures:
                    matched_ad_ids = structure.get('matched_ad_ids') or []

                    if matched_ad_ids:
                        ad_labels = [ad_stats['ad_names'].get(a, a) for a in matched_ad_ids]
                        print(f"   📍 Section at row {structure['header_row']}, col {structure['header_col']}: creatives {ad_labels}")
                        daily_data_to_write = _build_ad_scoped_daily_data(ad_stats, matched_ad_ids)
                    else:
                        # Plain section matched on the campaign's own ID (no
                        # creative IDs in its header) - full campaign totals.
                        print(f"   📍 Section at row {structure['header_row']}, col {structure['header_col']}: whole campaign")
                        daily_data_to_write = sape_client.get_daily_stats(
                            campaign_ids=[int(campaign.campaign_id)],
                            date_from=date_from,
                            date_to=date_to,
                            include_video_metrics=(campaign.format_type in ['V', 'CTV'])
                        )

                    if not daily_data_to_write:
                        print(f"   ⚠️ No data for this section")
                        continue

                    column_mapping = {
                        'date_column': structure['date_column'],
                        'impressions_column': structure['impressions_column'],
                        'reach_column': structure['reach_column'],
                        'clicks_column': structure['clicks_column'],
                        'ctr_column': structure['ctr_column'],
                        'vast25_column': None,
                        'vast50_column': None,
                        'vast75_column': None,
                        'completes_column': None
                    }

                    success = gs_client.write_daily_data(
                        sheet_url=report.google_sheet_url,
                        sheet_name=report.worksheet_name,
                        daily_data=daily_data_to_write,
                        column_mapping=column_mapping,
                        data_start_row=structure['data_start_row'],
                        daily_frequency=daily_frequency,
                        daily_variance=daily_variance,
                        total_frequency=total_frequency,
                        total_variance=total_variance,
                        frequency=daily_frequency,
                        frequency_variance=report.frequency_variance or 0.1,
                        total_reach_coefficient=report.total_reach_coefficient or 0.96,
                        cached_worksheet=cached_worksheet_object
                    )

                    if not success:
                        print(f"   ❌ Failed to write section")
                        continue

                    total_impressions += sum(d['impressions'] for d in daily_data_to_write)
                    total_clicks += sum(d['clicks'] for d in daily_data_to_write)
                    sections_written += 1

            if sections_written == 0:
                raise Exception("Не удалось найти/заполнить ни одной секции по креативам в Google таблице")

            log = ReportLog(
                report_config_id=report.id,
                status='success',
                metrics={
                    'total_impressions': total_impressions,
                    'total_clicks': total_clicks,
                    'sections_written': sections_written
                }
            )
            db.session.add(log)

            report.last_update = datetime.utcnow()
            db.session.commit()

            flash(f'Отчёт по креативам обновлён: {sections_written} секций. Всего показов: {total_impressions:,}, кликов: {total_clicks:,}', 'success')
            return redirect(url_for('reports'))

        # ==================== DAILY REPORT MODE (separate/combined) ====================
        total_impressions = 0
        total_clicks = 0
        total_days = 0

        # Build a map of campaign_id (SAPE ID) to Campaign object
        campaigns_by_sape_id = {str(c.campaign_id): c for c in campaigns}

        # Group campaigns by table section based on structure detection
        # We'll detect structure for each campaign and group by campaign_ids in header
        sections_to_process = {}  # {frozenset(campaign_ids): {structure, campaigns}}
        failed_campaign_ids = []  # Track which campaigns failed to be found

        print(f"\n{'='*60}")
        print(f"📋 Detecting table sections for {len(campaigns)} campaigns")
        print(f"   Report: {report.name or 'Unnamed'}")
        print(f"   Worksheet: '{report.worksheet_name}'")
        print(f"   Campaign IDs: {[c.campaign_id for c in campaigns]}")
        print(f"{'='*60}")

        # OPTIMIZATION: Open worksheet once and reuse for all operations
        # This reduces API calls from N to 1 (huge speedup + avoids quota limit!)
        print(f"📖 Opening worksheet once to cache for all operations...")
        cached_worksheet_object = gs_client.get_worksheet_object(
            sheet_url=report.google_sheet_url,
            sheet_name=report.worksheet_name
        )

        if cached_worksheet_object:
            print(f"✅ Cached worksheet object - will reuse for all operations (saves API quota)")
            # Read data once from cached worksheet
            cached_worksheet_data = cached_worksheet_object.get('A1:DZ300')
            print(f"✅ Cached {len(cached_worksheet_data)} rows of data")
            # DEBUG: Check if data is empty
            if len(cached_worksheet_data) == 0:
                print(f"⚠️ WARNING: Cached worksheet data is EMPTY! This will cause ID detection to fail.")
                print(f"   Worksheet name might be incorrect or sheet might be empty.")
        else:
            print(f"⚠️ Failed to cache worksheet, will read individually (slower)")
            cached_worksheet_data = None

        # Extract brand from sheet (auto-detection)
        print(f"\n🏷️ Attempting to extract brand from sheet...")
        brand_name = gs_client.extract_brand_from_sheet(
            sheet_url=report.google_sheet_url,
            sheet_name=report.worksheet_name,
            cached_worksheet=cached_worksheet_object
        )

        if brand_name:
            # Update report brand if found
            if report.brand != brand_name:
                print(f"✅ Brand extracted and updated: '{brand_name}' (was: '{report.brand or 'None'}')")
                report.brand = brand_name
                db.session.commit()
            else:
                print(f"✅ Brand already up to date: '{brand_name}'")
        else:
            print(f"⚠️ Brand not found in sheet (searched first 10 rows for 'Бренд')")

        # IMPORTANT: Find ALL sections for each campaign (a campaign may be in multiple sections)
        # Build a unique list of sections, identified by (header_row, header_col)
        sections_by_location = {}  # {(row, col): {structure, campaigns}}

        for idx, campaign in enumerate(campaigns, 1):
            print(f"\n🔍 [{idx}/{len(campaigns)}] Searching for campaign {campaign.campaign_id} ({campaign.name})")

            # Minimal delay since we use cached data (no API calls during detection)
            if idx > 1:
                import time
                time.sleep(0.1)

            # Find ALL sections containing this campaign (not just first one!)
            all_structures = gs_client.auto_detect_all_structures(
                sheet_url=report.google_sheet_url,
                sheet_name=report.worksheet_name,
                campaign_id=str(campaign.campaign_id),
                cached_data=cached_worksheet_data
            )

            if not all_structures:
                print(f"❌ Failed to find any sections for campaign {campaign.name} (ID: {campaign.campaign_id})")
                failed_campaign_ids.append(str(campaign.campaign_id))
                continue

            print(f"✅ Found {len(all_structures)} section(s) containing campaign {campaign.campaign_id}")

            # Add this campaign to each section where it appears
            for structure in all_structures:
                # Use (header_row, header_col) as unique section identifier
                section_location = (structure['header_row'], structure['header_col'])

                if section_location not in sections_by_location:
                    sections_by_location[section_location] = {
                        'structure': structure,
                        'campaigns': [],
                        'header_ids': structure.get('campaign_ids', [])
                    }
                    print(f"   📍 New section at row {structure['header_row']}, col {structure['header_col']}: IDs {structure.get('campaign_ids', [])}")

                # Add campaign to this section
                sections_by_location[section_location]['campaigns'].append(campaign)

        # Convert to the format expected by the rest of the code
        sections_to_process = {}
        for idx, (location, section_data) in enumerate(sections_by_location.items()):
            # Use index as key since we don't need frozenset anymore
            sections_to_process[idx] = section_data

        print(f"✅ Found {len(sections_to_process)} unique table sections")

        if len(sections_to_process) == 0:
            error_msg = f"Не удалось найти ни одной секции в Google таблице для выбранных кампаний.\n"
            error_msg += f"Лист: '{report.worksheet_name}'\n"
            error_msg += f"Искали ID: {', '.join(failed_campaign_ids[:10])}\n"

            # Try to find ANY 6-digit IDs in the table to help with debugging
            if cached_worksheet_data:
                import re
                all_ids_in_table = set()
                for row in cached_worksheet_data[:50]:  # Check first 50 rows
                    if not row:
                        continue
                    for cell in row:
                        if cell:
                            found = re.findall(r'(?:ID\s*)?(\d{6})\b', str(cell))
                            all_ids_in_table.update(found)

                if all_ids_in_table:
                    error_msg += f"ID найденные в таблице: {', '.join(sorted(list(all_ids_in_table))[:15])}\n"
                else:
                    error_msg += f"⚠️ В таблице не найдено ни одного 6-значного ID!\n"
                    error_msg += f"Возможно выбран неправильный лист или таблица пустая.\n"

            error_msg += f"Проверьте что ID кампаний присутствуют в заголовках таблицы.\n"
            error_msg += f"Система ищет 6-значные ID по всей таблице листа '{report.worksheet_name}'."
            print(f"❌ {error_msg}")
            raise Exception(error_msg)

        # Process each section
        section_counter = 0
        sections_processed = 0
        sections_failed = 0
        sections_skipped = 0  # Sections with fresh data
        failed_sections_details = []  # Store error details for user

        for section_key, section_data in sections_to_process.items():
            section_counter += 1
            print(f"\n🔍 DEBUG: Processing section {section_counter}/{len(sections_to_process)}")

            try:
                structure = section_data['structure']
                section_campaigns = section_data['campaigns']
                header_ids = section_data['header_ids']

                print(f"\n{'='*60}")
                if len(header_ids) > 1:
                    print(f"📊 COMBINED SECTION: {len(header_ids)} campaigns in header: {', '.join(header_ids)}")
                else:
                    print(f"📄 SEPARATE SECTION: Campaign {header_ids[0]}")
                print(f"{'='*60}")

                print(f"🔍 DEBUG: section_campaigns count: {len(section_campaigns)}")
                print(f"🔍 DEBUG: header_ids: {header_ids}")
                print(f"🔍 DEBUG: About to check video status...")

                # Determine if any campaign in this section is video (V or CTV)
                is_video = any(c.format_type in ['V', 'CTV'] for c in section_campaigns)
                print(f"🔍 DEBUG: is_video = {is_video}, len(header_ids) = {len(header_ids)}")

                # SMART RESUME temporarily disabled - fixing quota issues first
                # TODO: Re-enable after quota fix verified
                print(f"📝 Processing section...")

                # If multiple campaigns in header, sum their data
                if len(header_ids) > 1:
                    # COMBINED: Sum data from all campaigns in this section
                    combined_daily_stats = {}  # {date: {impressions, clicks, completes}}

                    for campaign_sape_id in header_ids:
                        # Find the campaign object
                        campaign = campaigns_by_sape_id.get(campaign_sape_id)
                        if not campaign:
                            print(f"⚠️ Campaign {campaign_sape_id} not found in selected campaigns")
                            continue

                        is_campaign_video = campaign.format_type in ['V', 'CTV']

                        daily_data = sape_client.get_daily_stats(
                            campaign_ids=[int(campaign_sape_id)],
                            date_from=date_from,
                            date_to=date_to,
                            include_video_metrics=is_campaign_video
                        )

                        if not daily_data:
                            print(f"⚠️ No data for campaign {campaign.name}")
                            continue

                        # Aggregate data by date
                        for day in daily_data:
                            date_key = day['date_iso']
                            if date_key not in combined_daily_stats:
                                base_data = {
                                    'date': day['date'],
                                    'date_iso': date_key,
                                    'impressions': 0,
                                    'clicks': 0,
                                    'ctr': 0
                                }
                                if is_video:
                                    # Initialize all video quartile metrics
                                    base_data['vastStart'] = 0
                                    base_data['vast25'] = 0
                                    base_data['vast50'] = 0
                                    base_data['vast75'] = 0
                                    base_data['completes'] = 0
                                combined_daily_stats[date_key] = base_data

                            combined_daily_stats[date_key]['impressions'] += day['impressions']
                            combined_daily_stats[date_key]['clicks'] += day['clicks']
                            if is_video:
                                # Sum all video quartile metrics when combining campaigns
                                if day.get('vastStart'):
                                    combined_daily_stats[date_key].setdefault('vastStart', 0)
                                    combined_daily_stats[date_key]['vastStart'] += day['vastStart']
                                if day.get('vast25') or day.get('vastFirstQuartile'):
                                    combined_daily_stats[date_key].setdefault('vast25', 0)
                                    combined_daily_stats[date_key]['vast25'] += day.get('vast25', day.get('vastFirstQuartile', 0))
                                if day.get('vast50') or day.get('vastMidpoint'):
                                    combined_daily_stats[date_key].setdefault('vast50', 0)
                                    combined_daily_stats[date_key]['vast50'] += day.get('vast50', day.get('vastMidpoint', 0))
                                if day.get('vast75') or day.get('vastThirdQuartile'):
                                    combined_daily_stats[date_key].setdefault('vast75', 0)
                                    combined_daily_stats[date_key]['vast75'] += day.get('vast75', day.get('vastThirdQuartile', 0))
                                if day.get('completes') or day.get('vastComplete'):
                                    combined_daily_stats[date_key].setdefault('completes', 0)
                                    combined_daily_stats[date_key]['completes'] += day.get('completes', day.get('vastComplete', 0))

                    # Convert to list and recalculate CTR
                    daily_data_to_write = []
                    for date_iso in sorted(combined_daily_stats.keys()):
                        day_data = combined_daily_stats[date_iso]
                        if day_data['impressions'] > 0:
                            day_data['ctr'] = round((day_data['clicks'] / day_data['impressions']) * 100, 2)
                        daily_data_to_write.append(day_data)

                    if not daily_data_to_write:
                        print(f"⚠️ No combined data for this section (campaigns: {', '.join(header_ids)})")
                        print(f"   Возможно SAPE API не вернул данные за период {date_from.strftime('%Y-%m-%d')} - {date_to.strftime('%Y-%m-%d')}")
                        continue

                    print(f"📊 Combined data: {len(daily_data_to_write)} days")

                    # Calculate average settings for combined campaigns (NEW)
                    # For COMBINED sections: use average of all campaigns' settings
                    daily_freqs = []
                    daily_vars = []
                    total_freqs = []
                    total_vars = []

                    for campaign_sape_id in header_ids:
                        campaign = campaigns_by_sape_id.get(campaign_sape_id)
                        if campaign:
                            cid_str = str(campaign.id)

                            # Try new format first (campaign_settings)
                            if report.campaign_settings and cid_str in report.campaign_settings:
                                settings = report.campaign_settings[cid_str]
                                daily_freqs.append(settings.get('daily_frequency', 3.0))
                                daily_vars.append(settings.get('daily_variance', 0.1))
                                total_freqs.append(settings.get('total_frequency', 3.0))
                                total_vars.append(settings.get('total_variance', 0.1))
                            # Fallback to old format
                            elif report.campaign_frequencies and cid_str in report.campaign_frequencies:
                                freq = report.campaign_frequencies[cid_str]
                                daily_freqs.append(freq)
                                daily_vars.append(report.frequency_variance or 0.1)
                                total_freqs.append(freq)
                                total_vars.append(0.1)
                            else:
                                # Default values
                                daily_freqs.append(3.0)
                                daily_vars.append(0.1)
                                total_freqs.append(3.0)
                                total_vars.append(0.1)

                    # Calculate averages
                    avg_daily_frequency = sum(daily_freqs) / len(daily_freqs) if daily_freqs else 3.0
                    avg_daily_variance = sum(daily_vars) / len(daily_vars) if daily_vars else 0.1
                    avg_total_frequency = sum(total_freqs) / len(total_freqs) if total_freqs else 3.0
                    avg_total_variance = sum(total_vars) / len(total_vars) if total_vars else 0.1

                    print(f"📊 COMBINED section averages:")
                    print(f"   Daily: freq={avg_daily_frequency:.2f}, var={avg_daily_variance:.2f}")
                    print(f"   Total: freq={avg_total_frequency:.2f}, var={avg_total_variance:.2f}")

                    # Keep for backward compatibility
                    avg_frequency = avg_daily_frequency

                else:
                # SEPARATE: Single campaign in this section
                    print(f"🔍 DEBUG: Entered SEPARATE section processing")
                    campaign = section_campaigns[0]
                    print(f"🔍 DEBUG: Campaign object: {campaign.name} (ID: {campaign.campaign_id})")
                    is_campaign_video = campaign.format_type in ['V', 'CTV']
                    print(f"🔍 DEBUG: is_campaign_video = {is_campaign_video}")

                    print(f"🔍 DEBUG: About to call get_daily_stats...")
                    daily_data_to_write = sape_client.get_daily_stats(
                        campaign_ids=[int(campaign.campaign_id)],
                        date_from=date_from,
                        date_to=date_to,
                        include_video_metrics=is_campaign_video
                    )
                    print(f"🔍 DEBUG: get_daily_stats returned: {len(daily_data_to_write) if daily_data_to_write else 'None/Empty'}")

                    if not daily_data_to_write:
                        print(f"⚠️ No data for campaign {campaign.name}")
                        continue

                    print(f"📊 Got {len(daily_data_to_write)} days of data")

                    # Get settings for this campaign (NEW)
                    cid_str = str(campaign.id)

                    # Try new format first (campaign_settings)
                    if report.campaign_settings and cid_str in report.campaign_settings:
                        settings = report.campaign_settings[cid_str]
                        avg_daily_frequency = settings.get('daily_frequency', 3.0)
                        avg_daily_variance = settings.get('daily_variance', 0.1)
                        avg_total_frequency = settings.get('total_frequency', 3.0)
                        avg_total_variance = settings.get('total_variance', 0.1)
                        print(f"📊 Using campaign_settings for campaign {campaign.id}")
                    # Fallback to old format
                    elif report.campaign_frequencies and cid_str in report.campaign_frequencies:
                        freq = report.campaign_frequencies[cid_str]
                        avg_daily_frequency = freq
                        avg_daily_variance = report.frequency_variance or 0.1
                        avg_total_frequency = freq
                        avg_total_variance = 0.1
                        print(f"📊 Using old format (fallback) for campaign {campaign.id}")
                    else:
                        # Default values
                        avg_daily_frequency = 3.0
                        avg_daily_variance = 0.1
                        avg_total_frequency = 3.0
                        avg_total_variance = 0.1
                        print(f"📊 Using default settings for campaign {campaign.id}")

                    print(f"   Daily: freq={avg_daily_frequency:.2f}, var={avg_daily_variance:.2f}")
                    print(f"   Total: freq={avg_total_frequency:.2f}, var={avg_total_variance:.2f}")

                    # Keep for backward compatibility
                    avg_frequency = avg_daily_frequency

                # Prepare column mapping
                # Use is_video (set for all sections) instead of is_campaign_video (only for SEPARATE)
                column_mapping = {
                    'date_column': structure['date_column'],
                    'impressions_column': structure['impressions_column'],
                    'reach_column': structure['reach_column'],
                    'clicks_column': structure['clicks_column'],
                    'ctr_column': structure['ctr_column'],
                    'vast25_column': structure.get('vast25_column') if is_video else None,
                    'vast50_column': structure.get('vast50_column') if is_video else None,
                    'vast75_column': structure.get('vast75_column') if is_video else None,
                    'completes_column': structure.get('completes_column') if is_video else None
                }

                # Write data to Google Sheets (using cached worksheet to save API quota)
                print(f"🔍 DEBUG: About to write {len(daily_data_to_write)} days to Google Sheets...")
                success = gs_client.write_daily_data(
                    sheet_url=report.google_sheet_url,
                    sheet_name=report.worksheet_name,  # Use worksheet from report config
                    daily_data=daily_data_to_write,
                    column_mapping=column_mapping,
                    data_start_row=structure['data_start_row'],
                    daily_frequency=avg_daily_frequency,
                    daily_variance=avg_daily_variance,
                    total_frequency=avg_total_frequency,
                    total_variance=avg_total_variance,
                    # OLD PARAMETERS (kept for backward compatibility, ignored in new logic):
                    frequency=avg_frequency,
                    frequency_variance=report.frequency_variance or 0.1,
                    total_reach_coefficient=report.total_reach_coefficient or 0.96,
                    cached_worksheet=cached_worksheet_object  # Pass cached worksheet
                )
                print(f"🔍 DEBUG: write_daily_data returned: {success}")

                if not success:
                    error_msg = f"Failed to write data for section {list(section_key)}"
                    print(f"❌ {error_msg}")
                    print(f"   Campaigns in section: {[campaigns_by_sape_id.get(cid).name for cid in header_ids if campaigns_by_sape_id.get(cid)]}")
                    print(f"   Data points to write: {len(daily_data_to_write)}")
                    print(f"   Worksheet: {report.worksheet_name}")
                    raise Exception(error_msg)

                # Accumulate metrics
                total_impressions += sum(d['impressions'] for d in daily_data_to_write)
                total_clicks += sum(d['clicks'] for d in daily_data_to_write)
                total_days += len(daily_data_to_write)
                sections_processed += 1
                print(f"🔍 DEBUG: Completed section {section_counter}/{len(sections_to_process)}. Total impressions so far: {total_impressions:,}")

                # Smart delay between sections to avoid API quota (60 req/min)
                # Each section makes ~7 API calls to Google Sheets
                # Strategy: Aggressive delays to avoid quota exceeded errors
                if section_counter < len(sections_to_process):
                    import time

                    # Calculate API calls made so far
                    api_calls_per_section = 7  # Approximate
                    total_calls_so_far = 1 + (sections_processed * api_calls_per_section)  # 1 = initial cache

                    # Google Sheets quota: 60 requests per minute
                    # For reports with 7+ campaigns, use aggressive delays
                    if len(sections_to_process) >= 7:
                        # For large reports: 3 second delay between sections
                        print(f"⏳ Large report protection ({len(sections_to_process)} sections): waiting 3 seconds...")
                        time.sleep(3)
                    elif total_calls_so_far >= 50:
                        # If we've made >= 50 calls, wait longer to stay safe
                        print(f"⏳ Quota protection: Made {total_calls_so_far} API calls, waiting 5 seconds...")
                        time.sleep(5)
                    elif total_calls_so_far >= 30:
                        # Medium risk: 3 second delay
                        print(f"⏳ Made {total_calls_so_far} API calls, waiting 3 seconds...")
                        time.sleep(3)
                    elif sections_processed >= 3:
                        # For any multi-section report, add delay every 3 sections
                        print(f"⏳ Periodic delay after {sections_processed} sections (2 sec)...")
                        time.sleep(2)
                    # else: No delay needed - proceed immediately!

            except Exception as section_error:
                campaign_names = [c.name for c in section_data.get('campaigns', [])]
                error_msg = str(section_error)

                # Check if this is a quota exceeded error (429)
                if '429' in error_msg or 'Quota exceeded' in error_msg or 'RATE_LIMIT_EXCEEDED' in error_msg:
                    print(f"⚠️ Google Sheets API quota exceeded (429) for section {section_counter}")
                    sections_failed += 1
                    failed_sections_details.append({
                        'campaigns': ', '.join(campaign_names[:3]),
                        'error': "Превышен лимит Google Sheets API (60 запросов/мин). Повторите обновление через 1-2 минуты."
                    })

                    # Add extra delay before next section to help quota recover
                    print(f"⏳ Adding 10 second delay to help quota recover...")
                    import time
                    time.sleep(10)
                else:
                    # Other errors - log and continue
                    sections_failed += 1
                    failed_sections_details.append({
                        'campaigns': ', '.join(campaign_names[:3]),  # First 3 campaign names
                        'error': error_msg[:100]  # First 100 chars of error
                    })

                    print(f"❌ ERROR processing section {section_counter}/{len(sections_to_process)}")
                    print(f"   Section campaigns: {campaign_names}")
                    print(f"   Error: {section_error}")
                    import traceback
                    traceback.print_exc()
                    print(f"   Continuing with next section...")

        print(f"\n🔍 DEBUG: Finished processing all {len(sections_to_process)} sections")
        print(f"   ✅ Successfully processed: {sections_processed}")
        print(f"   ⏭️  Skipped (fresh data): {sections_skipped}")
        print(f"   ❌ Failed: {sections_failed}")

        if total_days == 0:
            raise Exception("No statistics data for any campaign")

        # Calculate average CTR
        avg_ctr = round(total_clicks / total_impressions * 100, 2) if total_impressions > 0 else 0

        metrics = {
            'total_impressions': total_impressions,
            'total_clicks': total_clicks,
            'avg_ctr': avg_ctr,
            'days_updated': total_days,
            'campaigns_updated': len(campaigns)
        }

        # Log success
        log = ReportLog(
            report_config_id=report.id,
            status='success',
            metrics=metrics
        )
        db.session.add(log)

        report.last_update = datetime.utcnow()
        db.session.commit()

        success_msg = f'Отчет успешно обновлен для {len(campaigns)} кампаний. Секций обработано: {sections_processed}/{len(sections_to_process)}'
        if sections_skipped > 0:
            success_msg += f' (⏭️ пропущено с актуальными данными: {sections_skipped})'
        if sections_failed > 0:
            success_msg += f' (❌ не обработано: {sections_failed})'
            # Add details about failed sections
            for idx, fail_detail in enumerate(failed_sections_details[:2], 1):  # Show max 2 errors
                success_msg += f'\n  • Секция {idx}: {fail_detail["campaigns"]} - {fail_detail["error"]}'
        success_msg += f'. Всего показов: {total_impressions:,}, кликов: {total_clicks:,}'
        flash(success_msg, 'success' if sections_failed == 0 else 'warning')

    except Exception as e:
        # Log error
        log = ReportLog(
            report_config_id=report.id,
            status='error',
            error_message=str(e)
        )
        db.session.add(log)
        db.session.commit()

        flash(f'Ошибка при обновлении отчета: {str(e)}', 'error')

    return redirect(url_for('reports'))


@app.route('/reports/<int:report_id>/edit', methods=['GET', 'POST'])
def edit_report(report_id):
    """Edit existing report configuration"""
    report = ReportConfig.query.get_or_404(report_id)

    if request.method == 'POST':
        # Get form data
        report_name = request.form.get('report_name')
        manager = request.form.get('manager', '').strip() or None
        google_sheet_url = request.form.get('google_sheet_url')
        worksheet_name = request.form.get('worksheet_name', '').strip() or None
        campaign_ids_str = request.form.getlist('campaign_ids')
        campaign_mode = request.form.get('campaign_mode', 'separate')

        # Schedule
        schedule_days = request.form.get('schedule_days')
        schedule_time = request.form.get('schedule_time')
        report.schedule_enabled = request.form.get('schedule_enabled') == '1'

        # Update basic info
        url_changed = google_sheet_url and google_sheet_url != report.google_sheet_url

        # Update worksheet_name (can change independently from URL)
        if worksheet_name:  # Not None and not empty string
            worksheet_changed = worksheet_name != report.worksheet_name
            # ALWAYS update worksheet_name if provided from form
            report.worksheet_name = worksheet_name
        else:
            worksheet_changed = False
            # Keep existing worksheet_name if nothing provided

        if url_changed:
            report.google_sheet_url = google_sheet_url

        # Update campaigns FIRST before auto-detection
        if campaign_ids_str:
            campaign_ids = [int(cid) for cid in campaign_ids_str]
            report.campaign_ids = campaign_ids
            report.campaign_id = campaign_ids[0]  # Primary campaign

        # Re-detect structure if URL or worksheet changed (skip for 'total' mode reports)
        if url_changed or worksheet_changed:
            # Total mode reports don't have "Показатели кампании" headers, so auto-detection won't work
            if report.campaign_mode != 'total':
                # Use UPDATED campaign_ids from form (already updated above)
                campaigns = Campaign.query.filter(Campaign.id.in_(report.campaign_ids)).all()
                if campaigns:
                    gs_client = GoogleSheetsClient(
                        credentials_file=app.config['GOOGLE_CREDENTIALS_FILE'],
                        scopes=app.config['GOOGLE_SCOPES']
                    )

                    first_campaign = campaigns[0]
                    # Use updated worksheet_name from report (already saved above)
                    structure = gs_client.auto_detect_structure(
                        sheet_url=report.google_sheet_url,
                        sheet_name=report.worksheet_name,
                        campaign_id=first_campaign.campaign_id
                    )

                    if structure:
                        report.data_start_row = structure.get('data_start_row')
                        report.date_column = structure.get('date_column')
                        report.impressions_column = structure.get('impressions_column')
                        report.reach_column = structure.get('reach_column')
                        report.clicks_column = structure.get('clicks_column')
                        report.ctr_column = structure.get('ctr_column')
                        report.completes_column = structure.get('completes_column')
                        report.spent_column = structure.get('spent_column')
                    else:
                        flash(f'Не удалось определить структуру новой таблицы', 'warning')
            else:
                # For 'total' mode, structure is not needed (uses write_total_report_data)
                print(f"✓ Skipping structure detection for 'total' mode report")

        # Update campaign settings (frequencies, variances)
        campaign_settings = {}
        campaign_frequencies = {}  # Keep for backward compatibility

        for cid in campaign_ids:
            # Get new frequency settings (4 fields per campaign)
            daily_freq = request.form.get(f'daily_freq_{cid}', '3.0')
            daily_var = request.form.get(f'daily_var_{cid}', '0.1')
            total_freq = request.form.get(f'total_freq_{cid}', '3.0')
            total_var = request.form.get(f'total_var_{cid}', '0.1')

            try:
                daily_frequency = float(daily_freq)
                daily_variance = float(daily_var)
                total_frequency = float(total_freq)
                total_variance = float(total_var)

                # No validation - daily and total frequencies are independent parameters
                # User can set total_frequency higher or lower than daily_frequency

                campaign_settings[str(cid)] = {
                    'daily_frequency': daily_frequency,
                    'daily_variance': daily_variance,
                    'total_frequency': total_frequency,
                    'total_variance': total_variance
                }

                # Backward compatibility: save to old format too
                campaign_frequencies[str(cid)] = daily_frequency

            except ValueError:
                # Default values if parsing fails
                campaign_settings[str(cid)] = {
                    'daily_frequency': 3.0,
                    'daily_variance': 0.1,
                    'total_frequency': 3.0,
                    'total_variance': 0.1
                }
                campaign_frequencies[str(cid)] = 3.0

            # Update format if changed
            format_key = f'format_{cid}'
            format_value = request.form.get(format_key)
            if format_value:
                campaign = Campaign.query.get(cid)
                if campaign:
                    campaign.format_type = format_value

        # Save campaign settings
        report.campaign_settings = campaign_settings
        report.campaign_frequencies = campaign_frequencies  # Keep for backward compatibility
        report.frequency_variance = 0.1  # Default for backward compatibility

        # Update report name
        report.name = report_name.strip() if report_name and report_name.strip() else None

        report.campaign_mode = campaign_mode
        report.schedule_days = schedule_days
        report.schedule_time = schedule_time
        report.manager = manager

        db.session.commit()

        # Asana link lives on the report's linked monitoring, not on the
        # report itself - update it there, creating the monitoring if this
        # older report never got one auto-created. Only pull from Asana
        # when the link is newly added/changed, NOT on every report save -
        # otherwise every edit of an unrelated field (e.g. schedule time)
        # would silently re-overwrite the monitoring's date_from/date_to
        # with the Asana task's own dates, clobbering values deliberately
        # set differently for this specific monitoring. A retry after a
        # failed sync is done explicitly via the "Обновить" button on the
        # monitoring card (/monitoring/<id>/sync-asana), not implicitly here.
        asana_flash_shown = False
        asana_task_url = request.form.get('asana_task_url', '').strip() or None
        monitoring = MonitoringCampaign.query.filter_by(report_config_id=report.id).first()
        previous_asana_task_url = monitoring.asana_task_url if monitoring else None
        if asana_task_url or monitoring:
            if not monitoring:
                from datetime import timedelta
                today = datetime.now().date()
                monitoring = MonitoringCampaign(
                    name=report.name or report.campaign.name,
                    report_config_id=report.id,
                    account_id=report.campaign.account_id,
                    campaign_ids=report.campaign_ids,
                    date_from=today,
                    date_to=today + timedelta(days=30),
                    manager=report.manager,
                    google_sheet_url=report.google_sheet_url
                )
                db.session.add(monitoring)

            monitoring.asana_task_url = asana_task_url
            db.session.commit()

            if asana_task_url and asana_task_url != previous_asana_task_url:
                try:
                    from app.api.asana_client import AsanaClient
                    client = AsanaClient()
                    task_gid = client.extract_task_gid(asana_task_url)
                    if task_gid:
                        task = client.get_task(task_gid)
                        monitoring_campaigns = monitoring.get_campaigns()
                        format_type = monitoring_campaigns[0].format_type if monitoring_campaigns else None
                        format_idx = AsanaClient.format_index_for_campaign_type(format_type)
                        parsed = client.parse_monitoring_fields(task, format_idx=format_idx)
                        if parsed.get('task_date_from') and parsed.get('task_date_to'):
                            monitoring.date_from = parsed['task_date_from']
                            monitoring.date_to = parsed['task_date_to']
                            db.session.commit()

                    asana_result = _sync_monitoring_from_asana(monitoring)
                    db.session.commit()
                    flash(f'Отчет обновлён. План из Asana подтянут в мониторинг ({", ".join(asana_result["updated_fields"])})', 'success')
                    asana_flash_shown = True
                except AsanaSyncError as e:
                    flash(f'Отчет обновлён. Ссылка Asana сохранена, но план не подтянулся: {e}', 'warning')
                    asana_flash_shown = True
                except Exception as e:
                    db.session.rollback()
                    logging.error(f"⚠️ Unexpected error syncing Asana for monitoring {monitoring.id}: {e}")
                    flash('Отчет обновлён. Ссылка Asana сохранена, но при синхронизации произошла ошибка', 'warning')
                    asana_flash_shown = True

        if not asana_flash_shown:
            flash('Отчет успешно обновлен', 'success')
        return redirect(url_for('reports'))

    # GET request - show edit form
    account = report.campaign.account
    accounts = SapeAccount.query.filter_by(active=True).all()

    # Get all campaigns for this account
    campaigns = Campaign.query.filter_by(account_id=account.id, active=True).all()

    return render_template('edit_report.html',
                         report=report,
                         accounts=accounts,
                         account=account,
                         campaigns=campaigns)


@app.route('/reports/<int:report_id>/archive', methods=['POST'])
def archive_report(report_id):
    """Archive a report (hide from main view)"""
    report = ReportConfig.query.get_or_404(report_id)

    report.archived = True
    report.schedule_enabled = False

    # Archive the linked monitoring too, if this report has one
    monitoring = MonitoringCampaign.query.filter_by(report_config_id=report.id).first()
    if monitoring:
        monitoring.archived = True

    db.session.commit()

    flash(f'Отчет "{report.name or report.campaign.name}" перемещен в архив', 'success')
    return redirect(url_for('reports'))


@app.route('/reports/<int:report_id>/unarchive', methods=['POST'])
def unarchive_report(report_id):
    """Unarchive a report (restore to main view)"""
    report = ReportConfig.query.get_or_404(report_id)

    report.archived = False

    # Restore the linked monitoring too, if this report has one
    monitoring = MonitoringCampaign.query.filter_by(report_config_id=report.id).first()
    if monitoring:
        monitoring.archived = False

    db.session.commit()

    flash(f'Отчет "{report.name or report.campaign.name}" восстановлен из архива', 'success')
    return redirect(url_for('reports', show_archived='true'))


@app.route('/reports/bulk-archive', methods=['POST'])
@login_required
def bulk_archive_reports():
    """Archive multiple reports at once"""
    report_ids = (request.get_json(silent=True) or {}).get('report_ids', [])
    count = 0
    for report in ReportConfig.query.filter(ReportConfig.id.in_(report_ids)).all():
        report.archived = True
        report.schedule_enabled = False
        monitoring = MonitoringCampaign.query.filter_by(report_config_id=report.id).first()
        if monitoring:
            monitoring.archived = True
        count += 1
    db.session.commit()
    return jsonify({'success': True, 'count': count})


@app.route('/reports/bulk-delete', methods=['POST'])
@login_required
def bulk_delete_reports():
    """Permanently delete multiple reports at once"""
    report_ids = (request.get_json(silent=True) or {}).get('report_ids', [])
    count = 0
    for report in ReportConfig.query.filter(ReportConfig.id.in_(report_ids)).all():
        db.session.delete(report)
        count += 1
    db.session.commit()
    return jsonify({'success': True, 'count': count})


@app.route('/reports/<int:report_id>/copy')
def copy_report(report_id):
    """Copy a report with all settings"""
    original_report = ReportConfig.query.get_or_404(report_id)

    # Create a copy
    new_report = ReportConfig(
        campaign_id=original_report.campaign_id,
        campaign_ids=original_report.campaign_ids,
        campaign_mode=original_report.campaign_mode,
        google_sheet_url='',  # User will need to provide new sheet URL
        worksheet_name=None,  # User will need to select worksheet for new table
        data_start_row=None,  # Will be auto-detected when user selects worksheet
        date_column=None,
        impressions_column=None,
        reach_column=None,
        clicks_column=None,
        ctr_column=None,
        spent_column=None,
        completes_column=None,
        campaign_settings=original_report.campaign_settings,  # Copy campaign settings (frequencies)
        campaign_frequencies=original_report.campaign_frequencies,  # DEPRECATED: Keep for backward compatibility
        frequency_variance=original_report.frequency_variance,  # DEPRECATED: Keep for backward compatibility
        total_reach_coefficient=original_report.total_reach_coefficient,  # DEPRECATED: Keep for backward compatibility
        schedule_enabled=False,  # Disable schedule for copy by default
        schedule_days=original_report.schedule_days,
        schedule_time=original_report.schedule_time,
        manager=original_report.manager,
        active=True,
        archived=False
    )

    # Generate name for copy
    original_name = original_report.name or original_report.campaign.name
    new_report.name = f"{original_name} (копия)"

    db.session.add(new_report)
    db.session.commit()

    flash(f'Создана копия отчета "{original_name}". Укажите новую ссылку на Google Sheets.', 'success')
    return redirect(url_for('reports'))


# ==================== TEST API ENDPOINTS ====================

@app.route('/api/test/campaign/<int:campaign_id>/detail')
def test_campaign_detail(campaign_id):
    """
    Test endpoint to see full campaign detail response from SAPE API
    This shows all available fields including potential creative/banner data
    """
    campaign = Campaign.query.get_or_404(campaign_id)
    account = campaign.account

    # Initialize SAPE client
    sape_client = SapeAPIClient(
        login=account.login,
        token=account.token
    )

    if not sape_client.authenticate():
        return jsonify({
            'error': 'Failed to authenticate with SAPE API'
        }), 401

    # Get full campaign detail
    detail = sape_client.get_campaign_detail(campaign.campaign_id)

    if not detail:
        return jsonify({
            'error': 'Failed to get campaign detail'
        }), 500

    return jsonify({
        'campaign_id': campaign.campaign_id,
        'campaign_name': campaign.name,
        'account': account.name,
        'full_api_response': detail,
        'available_keys': list(detail.keys()) if isinstance(detail, dict) else None
    })


# ==================== DATABASE INITIALIZATION ====================

@app.cli.command()
def init_db():
    """Initialize database"""
    db.create_all()
    print("Database initialized!")


# ==================== SCHEDULED REPORTS ====================

def get_next_report_update_range(report):
    """
    Determine the date range the scheduler should write next: from the
    day right after whatever date was last written, through yesterday
    (we only ever have complete data up to yesterday - never "today").

    report.last_update is a run timestamp (set to "now" at the moment a
    run completes), and every run - manual or scheduled - always writes
    through "yesterday relative to that run". So the last day actually
    written is (last_update's date - 1 day), and the next day to write
    is last_update's date itself (no further +1 - a previous version of
    this function added an extra day here, which pushed daily schedules
    to write "today" instead of "yesterday").

    For schedules that run less often than daily (e.g. weekly), this
    returns the FULL gap since the last run, not just a single day, so
    nothing in between gets silently skipped.
    """
    from datetime import timedelta
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)

    if report.last_update:
        date_from = report.last_update.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        date_from = yesterday

    return date_from, yesterday


def run_report_update(report, date_from=None, date_to=None):
    """
    Run report update programmatically (for scheduled updates).

    Writes from the day after the sheet's last filled date through
    yesterday - covering the full gap since the last run (not just a
    single day), so repeated runs never re-write existing rows and
    nothing gets silently skipped for schedules that run less often
    than daily. Delegates to run_report_old's write logic (the same
    code path as the manual "Обновить сейчас" button) instead of
    duplicating the multi-section detection/write logic here.
    """
    try:
        if not date_from or not date_to:
            date_from, date_to = get_next_report_update_range(report)

        if date_from.date() > date_to.date():
            logging.info(f"ℹ️ Report {report.id} ({report.name or 'Unnamed'}) already up to date (next date {date_from.date()} is after yesterday {date_to.date()}), nothing to write")
            return True

        logging.info(f"🔄 Scheduled update for report {report.id} ({report.name or 'Unnamed'}): {date_from.strftime('%Y-%m-%d')} to {date_to.strftime('%Y-%m-%d')}")

        date_from_str = date_from.strftime('%Y-%m-%d')
        date_to_str = date_to.strftime('%Y-%m-%d')
        with app.test_request_context(
            f'/reports/{report.id}/run-old?date_from={date_from_str}&date_to={date_to_str}'
        ):
            run_report_old(report.id)

        logging.info(f"✅ Scheduled update completed for report {report.id}")
        return True

    except Exception as e:
        logging.error(f"❌ Error updating report {report.id}: {str(e)}")
        return False


def scheduled_update_reports():
    """
    Scheduled task to update reports based on their schedule settings
    Runs every hour and checks which reports should be updated
    """
    with app.app_context():
        now = datetime.now(pytz.timezone('Europe/Moscow'))
        current_day = now.isoweekday()  # 1=Monday, 7=Sunday
        current_hour = now.hour
        current_minute = now.minute

        logging.info(f"\n{'='*60}")
        logging.info(f"⏰ SCHEDULED REPORT CHECK - {now.strftime('%Y-%m-%d %H:%M:%S')}")
        logging.info(f"   Current day: {current_day} ({['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][current_day-1]}), Time: {current_hour:02d}:{current_minute:02d}")
        logging.info(f"{'='*60}")

        # Find all enabled scheduled reports
        scheduled_reports = ReportConfig.query.filter_by(
            schedule_enabled=True,
            active=True,
            archived=False
        ).all()

        if not scheduled_reports:
            logging.info("ℹ️ No scheduled reports found")
            return

        logging.info(f"📋 Found {len(scheduled_reports)} scheduled reports")

        reports_updated = 0
        reports_skipped = 0

        for report in scheduled_reports:
            # Check if report has schedule configured
            if not report.schedule_days or not report.schedule_time:
                logging.info(f"⏭️ Skipping report {report.id}: No schedule configured")
                reports_skipped += 1
                continue

            # Parse schedule days (e.g., "1,3,5" for Mon, Wed, Fri)
            try:
                scheduled_days = [int(d.strip()) for d in report.schedule_days.split(',') if d.strip()]
            except ValueError:
                logging.warning(f"⚠️ Invalid schedule_days format for report {report.id}: {report.schedule_days}")
                reports_skipped += 1
                continue

            # Check if today is a scheduled day
            if current_day not in scheduled_days:
                logging.debug(f"⏭️ Skipping report {report.id}: Today ({current_day}) not in schedule days {scheduled_days}")
                reports_skipped += 1
                continue

            # Parse schedule time (e.g., "09:30")
            try:
                scheduled_hour, scheduled_minute = map(int, report.schedule_time.split(':'))
            except ValueError:
                logging.warning(f"⚠️ Invalid schedule_time format for report {report.id}: {report.schedule_time}")
                reports_skipped += 1
                continue

            # Check if current time matches scheduled time exactly (job runs every minute)
            if current_hour == scheduled_hour and current_minute == scheduled_minute:
                logging.info(f"✅ Matched schedule for report {report.id} ({report.name or 'Unnamed'})")
                logging.info(f"   Scheduled: {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][current_day-1]} {scheduled_hour:02d}:{scheduled_minute:02d}")

                # Update the report
                success = run_report_update(report)
                if success:
                    reports_updated += 1
                else:
                    logging.error(f"❌ Failed to update report {report.id}")

                # Add delay after updating a report
                import time
                time.sleep(2)  # 2 seconds delay after each report update
            else:
                logging.debug(f"⏭️ Skipping report {report.id}: Time mismatch (scheduled {scheduled_hour:02d}:{scheduled_minute:02d}, current {current_hour:02d}:{current_minute:02d})")
                reports_skipped += 1

        logging.info(f"\n✅ SCHEDULED REPORT UPDATE COMPLETED:")
        logging.info(f"   Reports updated: {reports_updated}")
        logging.info(f"   Reports skipped: {reports_skipped}")
        logging.info(f"{'='*60}\n")


def scheduled_refresh_all_monitorings():
    """
    Scheduled task to refresh all active monitoring campaigns
    Runs daily at 09:00 and updates yesterday's data from SAPE API
    """
    with app.app_context():
        now = datetime.now(pytz.timezone('Europe/Moscow'))

        logging.info(f"\n{'='*60}")
        logging.info(f"⏰ SCHEDULED MONITORING REFRESH - {now.strftime('%Y-%m-%d %H:%M:%S')}")
        logging.info(f"{'='*60}")

        # Find all active monitorings (not archived)
        active_monitorings = MonitoringCampaign.query.filter_by(archived=False).all()

        if not active_monitorings:
            logging.info("ℹ️ No active monitorings found")
            return

        logging.info(f"📋 Found {len(active_monitorings)} active monitorings")

        monitorings_updated = 0
        monitorings_failed = 0

        for monitoring in active_monitorings:
            try:
                logging.info(f"🔄 Refreshing monitoring {monitoring.id}: {monitoring.name}")

                # Get campaigns
                campaigns = monitoring.get_campaigns()
                if not campaigns:
                    logging.warning(f"⚠️ No campaigns found for monitoring {monitoring.id}")
                    monitorings_failed += 1
                    continue

                # Get account
                account = monitoring.account
                if not account or not account.api_token:
                    logging.warning(f"⚠️ Account not configured for monitoring {monitoring.id}")
                    monitorings_failed += 1
                    continue

                # Initialize SAPE client
                client = SapeAPIClient(login=account.login, token=account.api_token)

                if not client.authenticate():
                    logging.error(f"❌ SAPE authentication failed for monitoring {monitoring.id}")
                    monitorings_failed += 1
                    continue

                # Get data from date_from to yesterday
                from datetime import timedelta
                yesterday = datetime.now() - timedelta(days=1)
                date_to = min(yesterday, datetime.combine(monitoring.date_to, datetime.min.time()))
                date_from = datetime.combine(monitoring.date_from, datetime.min.time())

                # Get campaign IDs
                campaign_ids = [int(c.campaign_id) for c in campaigns]

                # Request stats
                stats = client.get_stats(
                    campaign_ids=campaign_ids,
                    date_from=date_from,
                    date_to=date_to,
                    fields=None
                )

                if not stats:
                    logging.error(f"❌ Failed to get stats from SAPE for monitoring {monitoring.id}")
                    monitorings_failed += 1
                    continue

                # Extract totals
                total = stats.get('total', {})

                # Update monitoring with actual data
                monitoring.fact_impressions = total.get('shows', 0)
                monitoring.fact_clicks = total.get('clicks', 0)
                monitoring.fact_visits = total.get('visits', 0)
                monitoring.fact_bounce_rate = total.get('avgPostclickBounceRate', 0.0)
                monitoring.fact_time_on_site = total.get('avgVisitDuration', 0.0)
                monitoring.fact_page_depth = total.get('avgPostclickPageDepth', 0.0)
                monitoring.fact_robotness = total.get('avgPostclickRobot', 0.0)

                _refresh_verifier_campaign_facts(monitoring, client, date_from, date_to)
                _refresh_adriver_fact(monitoring, client, date_to)

                monitoring.last_sync = datetime.utcnow()

                db.session.commit()

                logging.info(f"✅ Monitoring {monitoring.id} refreshed: {monitoring.fact_impressions:,} impressions, {monitoring.fact_clicks:,} clicks, {monitoring.fact_visits:,} visits")
                monitorings_updated += 1

                # Add delay between requests to avoid rate limiting
                import time
                time.sleep(2)  # 2 seconds delay between each monitoring update

            except Exception as e:
                logging.error(f"❌ Error refreshing monitoring {monitoring.id}: {e}")
                monitorings_failed += 1
                import traceback
                traceback.print_exc()
                # Continue with next monitoring after error
                time.sleep(1)  # Short delay before next attempt
                continue

        logging.info(f"\n✅ SCHEDULED MONITORING REFRESH COMPLETED:")
        logging.info(f"   Monitorings updated: {monitorings_updated}")
        logging.info(f"   Monitorings failed: {monitorings_failed}")
        logging.info(f"{'='*60}\n")


def scheduled_refresh_weborama_verifiers():
    """
    Scheduled task to refresh every Weborama verifier permalink daily.

    Runs after scheduled_refresh_all_monitorings so the discrepancy %
    compares against fresh SAPE fact data. Each link is its own headless
    browser session (~20-25s) run one at a time - this IS the queue: a
    plain sequential loop where a single broken/unreachable permalink is
    caught, logged, and skipped without blocking the rest of the links
    or crashing the job. No external queue/worker needed - the daily
    cron interval already de-duplicates retries, and misfire_grace_time
    on the job below covers a missed run.
    """
    with app.app_context():
        now = datetime.now(pytz.timezone('Europe/Moscow'))
        logging.info(f"\n{'='*60}")
        logging.info(f"⏰ SCHEDULED WEBORAMA VERIFIER REFRESH - {now.strftime('%Y-%m-%d %H:%M:%S')}")
        logging.info(f"{'='*60}")

        links = (VerifierLink.query
                 .join(MonitoringCampaign)
                 .filter(VerifierLink.verifier_type == 'weborama')
                 .filter(VerifierLink.permalink_url.isnot(None))
                 .filter(MonitoringCampaign.archived == False)
                 .all())

        if not links:
            logging.info("ℹ️ No Weborama verifier permalinks found")
            return

        logging.info(f"📋 Found {len(links)} Weborama permalink(s) to refresh")

        import time
        updated = 0
        failed = 0

        for link in links:
            try:
                result = _fetch_and_apply_weborama_link(link)
                mapping_summary = ', '.join(
                    f"{m.get('insertion_name') or ('mapping ' + str(m['id']))}={'OK' if m['success'] else 'ERR'}"
                    for m in result['mappings']
                ) or 'нет сопоставлений'
                logging.info(f"✅ Weborama link {link.id} ({link.monitoring.name}): {mapping_summary}")
                updated += 1
            except WeboramaLinkFetchError as e:
                logging.warning(f"⚠️ Weborama link {link.id} ({link.monitoring.name}) skipped: {e}")
                failed += 1
            except Exception as e:
                logging.error(f"❌ Weborama link {link.id} ({link.monitoring.name}) failed: {e}")
                db.session.rollback()
                failed += 1

            time.sleep(2)  # short breather between browser sessions

        logging.info(f"\n✅ SCHEDULED WEBORAMA VERIFIER REFRESH COMPLETED:")
        logging.info(f"   Links updated: {updated}")
        logging.info(f"   Links failed: {failed}")
        logging.info(f"{'='*60}\n")


# ==================== SCHEDULER ====================

# Initialize and start scheduler only when enabled
# For production: set ENABLE_AUTO_SYNC=1 environment variable
# For local development: disabled by default to prevent database locks
import sys
ENABLE_AUTO_SYNC = os.getenv('ENABLE_AUTO_SYNC', '0') == '1'

# With multiple gunicorn workers, each worker process would otherwise start
# its own independent scheduler, running every job redundantly in parallel
# (e.g. hitting the SAPE API N times at once for the same report). Use a
# non-blocking file lock so only the first worker to grab it runs the
# scheduler; the lock is released automatically if that worker dies.
_scheduler_lock_acquired = False
if 'flask' not in sys.argv[0] and ENABLE_AUTO_SYNC:
    import fcntl
    _scheduler_lock_file = open(os.path.join(os.path.dirname(__file__), '.scheduler.lock'), 'w')
    try:
        fcntl.flock(_scheduler_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _scheduler_lock_acquired = True
    except (IOError, OSError):
        logging.info("ℹ️ Scheduler already running in another worker, skipping here")

if 'flask' not in sys.argv[0] and ENABLE_AUTO_SYNC and _scheduler_lock_acquired:
    try:
        scheduler = BackgroundScheduler(timezone=pytz.timezone('Europe/Moscow'))

        # Add weekday sync job at 09:00 (Monday-Friday, working hours)
        scheduler.add_job(
            func=scheduled_sync_all_accounts,
            trigger=CronTrigger(day_of_week='mon-fri', hour=9, minute=0),
            id='daily_sync_accounts',
            name='Синхронизация всех аккаунтов SAPE',
            replace_existing=True,
            misfire_grace_time=3600,  # Run within 1 hour if missed
            coalesce=True,  # Combine multiple missed runs into one
            max_instances=1  # Don't run multiple instances simultaneously
        )

        # Add report update check (runs every minute so staggered schedule_time
        # values, e.g. 09:03/09:07/09:11, actually get matched and triggered)
        scheduler.add_job(
            func=scheduled_update_reports,
            trigger=CronTrigger(minute='*'),  # Run every minute
            id='hourly_reports_check',
            name='Проверка расписания обновления отчетов',
            replace_existing=True,
            misfire_grace_time=60,
            coalesce=True,  # Combine multiple missed runs into one
            max_instances=1  # Don't run multiple instances simultaneously
        )

        # Add daily monitoring refresh at 08:00 - pushed later than the
        # original 03:00 because SAPE's own report data for "yesterday"
        # isn't fully settled that early; running at 03:00 risked pulling
        # a partial fact.
        scheduler.add_job(
            func=scheduled_refresh_all_monitorings,
            trigger=CronTrigger(hour=8, minute=0),
            id='daily_monitoring_refresh',
            name='Автообновление данных мониторинга',
            replace_existing=True,
            misfire_grace_time=3600,  # Run within 1 hour if missed
            coalesce=True,  # Combine multiple missed runs into one
            max_instances=1  # Don't run multiple instances simultaneously
        )

        # Add daily Weborama verifier refresh at 08:30 - after the SAPE
        # fact refresh above, so discrepancy % compares against fresh data
        scheduler.add_job(
            func=scheduled_refresh_weborama_verifiers,
            trigger=CronTrigger(hour=8, minute=30),
            id='daily_weborama_verifier_refresh',
            name='Автообновление верификаторов Weborama',
            replace_existing=True,
            misfire_grace_time=3600,
            coalesce=True,
            max_instances=1
        )

        # Start scheduler
        scheduler.start()
        logging.info("✅ Scheduler started:")
        logging.info("   - Weekday account sync at 09:00 Moscow time (Mon-Fri)")
        logging.info("   - Hourly report schedule check (every hour at :00)")
        logging.info("   - Daily monitoring refresh at 08:00 Moscow time (every day)")
        logging.info("   - Daily Weborama verifier refresh at 08:30 Moscow time (every day)")

        # Check if we need to sync on startup (if last sync was >24h ago)
        if should_sync_on_startup():
            logging.info("🚀 Running sync on startup...")
            import threading
            # Run in separate thread to not block startup
            sync_thread = threading.Thread(target=scheduled_sync_all_accounts)
            sync_thread.daemon = True
            sync_thread.start()
    except Exception as e:
        print(f"⚠️ Warning: Could not start scheduler: {e}")
else:
    if not ENABLE_AUTO_SYNC:
        logging.info("ℹ️ Auto-sync disabled (ENABLE_AUTO_SYNC=0). Use manual sync from UI.")


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # threaded=True so a slow request (e.g. the ~20-40s Weborama permalink
    # fetch, which drives a real headless browser) doesn't block every
    # other request on this single-process dev server - without it the
    # whole local app appears frozen until that one request finishes.
    # Production runs under gunicorn with multiple workers instead, which
    # already doesn't have this problem - this line only runs for local
    # `python app.py`, never under gunicorn's WSGI entry point.
    app.run(debug=False, host='0.0.0.0', port=5006, use_reloader=False, threaded=True)
