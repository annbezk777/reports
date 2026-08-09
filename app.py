from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from functools import wraps
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime
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
from app.models import db, SapeAccount, Client, Campaign, ReportConfig, ReportLog
db.init_app(app)
migrate = Migrate(app, db)

# Import API clients
from app.api.sape_client import SapeAPIClient
from app.api.google_sheets_client import GoogleSheetsClient






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
def register():
    """Registration page"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        password_confirm = request.form.get('password_confirm', '').strip()

        # Validation
        if not email.endswith('@sape.ru'):
            flash('Email должен заканчиваться на @sape.ru', 'error')
            return render_template('register.html')

        if len(password) < 6:
            flash('Пароль должен содержать минимум 6 символов', 'error')
            return render_template('register.html')

        if password != password_confirm:
            flash('Пароли не совпадают', 'error')
            return render_template('register.html')

        # Check if user exists
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            flash('Пользователь с таким email уже существует', 'error')
            conn.close()
            return render_template('register.html')

        # Generate verification code
        verification_code = str(random.randint(100000, 999999))
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        # Create user
        cursor.execute('''
INSERT INTO users (email, password_hash, verification_code, email_verified, active)
VALUES (?, ?, ?, 0, 1)
''', (email, password_hash, verification_code))
        conn.commit()
        conn.close()

        # Send verification email
        if send_verification_email(email, verification_code):
            flash('Регистрация успешна! Проверьте почту и введите код подтверждения.', 'success')
            return redirect(url_for('verify_email') + f'?email={email}')
        else:
            flash('Ошибка отправки email. Код: ' + verification_code, 'error')
            return redirect(url_for('verify_email') + f'?email={email}')

    return render_template('register.html')


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


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Forgot password page"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        if not email.endswith('@sape.ru'):
            flash('Email должен заканчиваться на @sape.ru', 'error')
            return render_template('forgot_password.html')

        # Check if user exists
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, email FROM users WHERE email = ? AND active = 1', (email,))
        user = cursor.fetchone()

        if user:
            # Generate reset token (6-digit code)
            reset_token = str(random.randint(100000, 999999))

            # Set expiration time (1 hour from now)
            from datetime import datetime, timedelta
            expires = datetime.utcnow() + timedelta(hours=1)

            # Save token to database
            cursor.execute(
                'UPDATE users SET reset_token = ?, reset_token_expires = ? WHERE email = ?',
                (reset_token, expires.isoformat(), email)
            )
            conn.commit()

            # Send email with reset code
            email_sent = False
            try:
                msg = MIMEMultipart()
                msg['From'] = SMTP_EMAIL
                msg['To'] = email
                msg['Subject'] = 'Восстановление пароля - SAPE Reports Panel'

                body = f"""
Здравствуйте!

Вы запросили восстановление пароля для панели отчетов SAPE.

Ваш код для сброса пароля: {reset_token}

Код действителен в течение 1 часа.

Перейдите по ссылке для ввода кода и нового пароля:
http://localhost:5006/reset-password

Если вы не запрашивали восстановление пароля, просто проигнорируйте это письмо.

--
SAPE Reports Panel
                """

                msg.attach(MIMEText(body, 'plain', 'utf-8'))

                server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
                server.starttls()
                if SMTP_PASSWORD:
                    server.login(SMTP_EMAIL, SMTP_PASSWORD)
                server.send_message(msg)
                server.quit()
                email_sent = True

            except Exception as e:
                print(f"Error sending reset email: {e}")
                # Don't show error - just display code instead
                email_sent = False

            if email_sent:
                flash(f'Код восстановления отправлен на {email}', 'success')
            else:
                # If email failed, show code directly (for development)
                flash(f'SMTP не настроен. Ваш код восстановления: {reset_token}', 'info')
                print(f"🔑 RESET CODE for {email}: {reset_token}")

            return redirect(url_for('reset_password'))
        else:
            # Don't reveal if user exists or not (security)
            flash(f'Если пользователь существует, код восстановления отправлен на {email}', 'info')
            return redirect(url_for('reset_password'))

        conn.close()

    return render_template('forgot_password.html')


@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    """Reset password with token"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        reset_token = request.form.get('reset_token', '').strip()
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        # Validation
        if not email.endswith('@sape.ru'):
            flash('Email должен заканчиваться на @sape.ru', 'error')
            return render_template('reset_password.html')

        if len(new_password) < 6:
            flash('Пароль должен содержать минимум 6 символов', 'error')
            return render_template('reset_password.html')

        if new_password != confirm_password:
            flash('Пароли не совпадают', 'error')
            return render_template('reset_password.html')

        # Check token
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, reset_token_expires FROM users WHERE email = ? AND reset_token = ? AND active = 1',
            (email, reset_token)
        )
        user = cursor.fetchone()

        if user:
            # Check if token expired
            from datetime import datetime
            expires = datetime.fromisoformat(user['reset_token_expires'])

            if datetime.utcnow() > expires:
                flash('Код восстановления истек. Запросите новый код.', 'error')
                conn.close()
                return redirect(url_for('forgot_password'))

            # Update password
            password_hash = hashlib.sha256(new_password.encode()).hexdigest()
            cursor.execute(
                'UPDATE users SET password_hash = ?, reset_token = NULL, reset_token_expires = NULL WHERE email = ?',
                (password_hash, email)
            )
            conn.commit()
            conn.close()

            flash('Пароль успешно изменен! Войдите с новым паролем.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Неверный email или код восстановления', 'error')
            conn.close()

    return render_template('reset_password.html')


# ==================== ROUTES ====================

@app.route('/')
@login_required
def index():
    """Main dashboard"""
    accounts_count = SapeAccount.query.filter_by(active=True).count()
    campaigns_count = Campaign.query.filter_by(active=True).count()
    reports_count = ReportConfig.query.filter_by(active=True).count()
    
    recent_logs = ReportLog.query.order_by(ReportLog.executed_at.desc()).limit(10).all()
    
    return render_template('index.html',
                         accounts_count=accounts_count,
                         campaigns_count=campaigns_count,
                         reports_count=reports_count,
                         recent_logs=recent_logs)


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

        flash(f'Аккаунт "{name}" успешно добавлен', 'success')
        return redirect(url_for('accounts'))

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
    """Sync campaigns from SAPE"""
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

        # Get detailed campaign info to fetch clientId and type
        campaign_detail = client.get_campaign_detail(camp['id'])
        sape_client_id = None
        sape_type = None
        if campaign_detail:
            sape_client_id = campaign_detail.get('clientId')
            sape_type = campaign_detail.get('type')  # Get campaign type from API

        # Detect format using SAPE API type (preferred) or name (fallback)
        format_type = detect_campaign_format(campaign_name, sape_type)

        # Find client in our DB
        db_client = None
        if sape_client_id:
            db_client = Client.query.filter_by(
                account_id=account.id,
                client_id=str(sape_client_id)
            ).first()

        # Check if campaign exists
        campaign = Campaign.query.filter_by(
            account_id=account.id,
            campaign_id=str(camp['id'])
        ).first()

        if not campaign:
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
            # Update existing campaign
            campaign.name = campaign_name
            campaign.format_type = format_type
            campaign.client_id = db_client.id if db_client else None
            updated_count += 1

    # Update last sync time
    account.last_sync = datetime.utcnow()
    db.session.commit()

    flash(f'Синхронизировано: {clients_synced} клиентов, {synced_count} новых кампаний, обновлено {updated_count} кампаний', 'success')
    return redirect(url_for('accounts'))


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

            # Get campaign details for client ID and type
            campaign_detail = client.get_campaign_detail(camp['id'])
            sape_client_id = None
            sape_type = None
            if campaign_detail:
                sape_client_id = campaign_detail.get('clientId')
                sape_type = campaign_detail.get('type')  # Get campaign type from API

            # Detect format using SAPE API type (preferred) or name (fallback)
            format_type = detect_campaign_format(campaign_name, sape_type)

            # Find client in DB
            db_client = None
            if sape_client_id:
                db_client = Client.query.filter_by(
                    account_id=account.id,
                    client_id=str(sape_client_id)
                ).first()

            # Check if campaign exists
            campaign = Campaign.query.filter_by(
                account_id=account.id,
                campaign_id=str(camp['id'])
            ).first()

            if not campaign:
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
                campaign.name = campaign_name
                campaign.format_type = format_type
                campaign.client_id = db_client.id if db_client else None
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

    return render_template('reports.html', reports=all_reports, show_archived=show_archived, manager_filter=manager_filter)


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

                # Validation: total_frequency <= daily_frequency
                if total_frequency > daily_frequency:
                    total_frequency = daily_frequency

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
            schedule_enabled=True,
            manager=manager
        )

        db.session.add(report)
        db.session.commit()

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
        flash(f'Отчет успешно создан для кампаний: {campaign_names}. Режим: {"Раздельно" if campaign_mode == "separate" else "Едино"}', 'success')
        return redirect(url_for('reports'))

    # Get all accounts for dropdown
    accounts = SapeAccount.query.filter_by(active=True).all()
    return render_template('add_report.html', accounts=accounts)


@app.route('/reports/<int:report_id>/run')
def run_report(report_id):
    """Run report manually"""
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
                import random
                min_freq = max(frequency - total_variance, 0.1)
                max_freq = frequency + total_variance
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

                print(f"✅ Campaign {campaign.campaign_id} ({campaign.name}):")
                print(f"   Shows: {period_shows:,}, Clicks: {period_clicks:,}")
                print(f"   Frequency target: {frequency} ± {total_variance}, actual: {actual_frequency:.2f}")
                print(f"   Average daily reach: {average_reach:,} (from {len(daily_reaches)} days)")

                campaigns_data.append({
                    'campaign_id': campaign.campaign_id,
                    'shows': period_shows,
                    'clicks': period_clicks,
                    'frequency': frequency,
                    'average_reach': average_reach  # NEW: pass average reach instead of calculating from total
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

        # Re-detect structure if URL or worksheet changed (skip for 'total' mode reports)
        if url_changed or worksheet_changed:
            # Total mode reports don't have "Показатели кампании" headers, so auto-detection won't work
            if report.campaign_mode != 'total':
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

        # Update campaigns if changed
        if campaign_ids_str:
            campaign_ids = [int(cid) for cid in campaign_ids_str]
            report.campaign_ids = campaign_ids
            report.campaign_id = campaign_ids[0]  # Primary campaign

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
    db.session.commit()

    flash(f'Отчет "{report.name or report.campaign.name}" перемещен в архив', 'success')
    return redirect(url_for('reports'))


@app.route('/reports/<int:report_id>/unarchive', methods=['POST'])
def unarchive_report(report_id):
    """Unarchive a report (restore to main view)"""
    report = ReportConfig.query.get_or_404(report_id)

    report.archived = False
    db.session.commit()

    flash(f'Отчет "{report.name or report.campaign.name}" восстановлен из архива', 'success')
    return redirect(url_for('reports', show_archived='true'))


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
        worksheet_name=original_report.worksheet_name,
        data_start_row=original_report.data_start_row,
        date_column=original_report.date_column,
        impressions_column=original_report.impressions_column,
        reach_column=original_report.reach_column,
        clicks_column=original_report.clicks_column,
        ctr_column=original_report.ctr_column,
        spent_column=original_report.spent_column,
        completes_column=original_report.completes_column,
        campaign_settings=original_report.campaign_settings,  # NEW: Copy campaign settings
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
    return redirect(url_for('edit_report', report_id=new_report.id))


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


# ==================== SCHEDULER ====================

# Initialize and start scheduler only when enabled
# For production: set ENABLE_AUTO_SYNC=1 environment variable
# For local development: disabled by default to prevent database locks
import sys
ENABLE_AUTO_SYNC = os.getenv('ENABLE_AUTO_SYNC', '0') == '1'

if 'flask' not in sys.argv[0] and ENABLE_AUTO_SYNC:
    try:
        scheduler = BackgroundScheduler(timezone=pytz.timezone('Europe/Moscow'))

        # Add daily sync job at 10:00 (working hours)
        scheduler.add_job(
            func=scheduled_sync_all_accounts,
            trigger=CronTrigger(hour=10, minute=0),
            id='daily_sync_accounts',
            name='Синхронизация всех аккаунтов SAPE',
            replace_existing=True,
            misfire_grace_time=3600,  # Run within 1 hour if missed
            coalesce=True,  # Combine multiple missed runs into one
            max_instances=1  # Don't run multiple instances simultaneously
        )

        # Start scheduler
        scheduler.start()
        logging.info("✅ Scheduler started: Daily account sync at 10:00 Moscow time")

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


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=False, host='0.0.0.0', port=5006, use_reloader=False)
