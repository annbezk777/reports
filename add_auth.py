#!/usr/bin/env python3
"""
Add authentication to app.py with login@sape.ru format
"""

def add_auth():
    with open('app.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # Check if auth already added
    if 'def login_required' in content:
        print("⚠️  Authentication already exists in app.py")
        return

    # Find the imports section and add functools
    imports_section = "from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session"
    new_imports = "from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session\nfrom functools import wraps"

    content = content.replace(imports_section, new_imports)

    # Add auth decorator and login/logout routes after the imports and before routes
    auth_code = '''

# ==================== AUTHENTICATION ====================

# Authorized users (login: password)
# Login must be in format: *@sape.ru
AUTHORIZED_USERS = {
    'a.bereznyak@sape.ru': os.environ.get('SAPE_REPORTS_PASSWORD', 'sape2024'),
    # Add more users as needed
}

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
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        # Check username format
        if not username.endswith('@sape.ru'):
            flash('Логин должен быть в формате: user@sape.ru', 'error')
            return render_template('login.html')

        # Check credentials
        if username in AUTHORIZED_USERS and AUTHORIZED_USERS[username] == password:
            session['logged_in'] = True
            session['username'] = username
            session.permanent = True

            flash(f'Добро пожаловать, {username}!', 'success')

            # Redirect to next page or index
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('index'))
        else:
            flash('Неверный логин или пароль', 'error')

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout"""
    username = session.get('username', 'Пользователь')
    session.pop('logged_in', None)
    session.pop('username', None)
    flash(f'{username} вышел из системы', 'success')
    return redirect(url_for('login'))

'''

    # Insert auth code before "# ==================== ROUTES ===================="
    routes_marker = "# ==================== ROUTES ===================="
    content = content.replace(routes_marker, auth_code + routes_marker)

    # Add @login_required to all routes except login and logout
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
        # Add @login_required before each route
        content = content.replace(
            route + "\ndef",
            route + "\n@login_required\ndef"
        )

    # Write updated content
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)

    print("✅ Authentication added to app.py")
    print("")
    print("📝 Authorized users:")
    print("   Login: a.bereznyak@sape.ru")
    print("   Password: sape2024 (or set SAPE_REPORTS_PASSWORD env var)")
    print("")
    print("⚠️  To add more users, edit AUTHORIZED_USERS dictionary in app.py")


if __name__ == '__main__':
    add_auth()
