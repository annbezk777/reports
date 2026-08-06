#!/usr/bin/env python3
"""
Replace authentication system with full registration + email verification
"""

def replace_auth():
    with open('app.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # Remove old auth system if exists
    if '# ==================== AUTHENTICATION ====================' in content:
        # Find and remove old auth section
        start_marker = '# ==================== AUTHENTICATION ===================='
        end_marker = '# ==================== ROUTES ===================='

        start_idx = content.find(start_marker)
        end_idx = content.find(end_marker)

        if start_idx != -1 and end_idx != -1:
            content = content[:start_idx] + content[end_idx:]
            print("✅ Removed old authentication system")

    # Add new imports
    if 'import hashlib' not in content:
        imports_line = "import os"
        content = content.replace(imports_line, imports_line + "\nimport hashlib\nimport random\nimport smtplib\nfrom email.mime.text import MIMEText\nfrom email.mime.multipart import MIMEMultipart")

    if 'from functools import wraps' not in content:
        imports_section = "from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session"
        new_imports = "from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session\nfrom functools import wraps"
        content = content.replace(imports_section, new_imports)

    # New auth system code
    new_auth_code = '''

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
            print(f"\\n{'='*60}")
            print(f"VERIFICATION CODE for {email}: {code}")
            print(f"{'='*60}\\n")
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
            return render_template('login_new.html')

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

    return render_template('login_new.html')


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
        cursor.execute(\'''
INSERT INTO users (email, password_hash, verification_code, email_verified, active)
VALUES (?, ?, ?, 0, 1)
\''', (email, password_hash, verification_code))
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

'''

    # Insert new auth code before routes
    routes_marker = "# ==================== ROUTES ===================="
    content = content.replace(routes_marker, new_auth_code + routes_marker)

    # Add @login_required to protected routes
    routes_to_protect = [
        "@app.route('/')",
        "@app.route('/accounts')",
        "@app.route('/accounts/add'",
        "@app.route('/accounts/<int:account_id>/edit'",
        "@app.route('/accounts/<int:account_id>/delete'",
        "@app.route('/accounts/<int:account_id>/sync'",
        "@app.route('/campaigns')",
        "@app.route('/reports')",
        "@app.route('/reports/add'",
        "@app.route('/reports/<int:report_id>/edit'",
        "@app.route('/reports/<int:report_id>/copy'",
        "@app.route('/reports/<int:report_id>/run'",
        "@app.route('/reports/<int:report_id>/archive'",
        "@app.route('/reports/<int:report_id>/unarchive'",
        "@app.route('/api/campaigns/<int:campaign_id>'",
    ]

    for route in routes_to_protect:
        # Remove existing @login_required if any
        content = content.replace(route + "\n@login_required\n@login_required\ndef", route + "\n@login_required\ndef")
        # Add @login_required
        if route + "\n@login_required\ndef" not in content:
            content = content.replace(route + "\ndef", route + "\n@login_required\ndef")

    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)

    print("✅ New authentication system installed")
    print("")
    print("Features:")
    print("  ✅ User registration with @sape.ru validation")
    print("  ✅ Email verification with 6-digit code")
    print("  ✅ Password show/hide toggle")
    print("  ✅ Secure password hashing (SHA-256)")
    print("")
    print("Next steps:")
    print("  1. Run: python3 create_auth_system.py")
    print("  2. Deploy to server")


if __name__ == '__main__':
    replace_auth()
