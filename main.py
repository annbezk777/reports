from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime
import os
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

# Import configuration
from config import Config

# Initialize Flask app
app = Flask(__name__,
           template_folder='app/templates',
           static_folder='app/static')
app.config.from_object(Config)

# Initialize database
from app.models import db, SapeAccount, Client, Campaign, ReportConfig, ReportLog
db.init_app(app)
migrate = Migrate(app, db)

# Import API clients
from app.api.sape_client import SapeAPIClient
from app.api.google_sheets_client import GoogleSheetsClient


# ==================== ROUTES ====================

@app.route('/')
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

        if not name or not login or not api_token:
            flash('Все поля обязательны для заполнения', 'error')
            return render_template('add_account.html')

        # Create new account
        account = SapeAccount(
            name=name,
            login=login,
            api_token=api_token
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

        if not name or not login or not api_token:
            flash('Все поля обязательны для заполнения', 'error')
            return render_template('edit_account.html', account=account)

        account.name = name
        account.login = login
        account.api_token = api_token

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


def scheduled_sync_all_accounts():
    """Scheduled task to sync all accounts (runs at 00:00 daily)"""
    with app.app_context():
        print(f"\n{'='*60}")
        print(f"⏰ SCHEDULED SYNC - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")

        accounts = SapeAccount.query.filter_by(active=True).all()

        if not accounts:
            print("ℹ️ No active accounts to sync")
            return

        print(f"🔄 Syncing {len(accounts)} accounts...")

        total_clients = 0
        total_new_campaigns = 0
        total_updated_campaigns = 0

        for account in accounts:
            result = sync_single_account(account)

            if result['success']:
                total_clients += result.get('clients_synced', 0)
                total_new_campaigns += result.get('campaigns_new', 0)
                total_updated_campaigns += result.get('campaigns_updated', 0)

        print(f"\n✅ SCHEDULED SYNC COMPLETED:")
        print(f"   Total clients: {total_clients}")
        print(f"   New campaigns: {total_new_campaigns}")
        print(f"   Updated campaigns: {total_updated_campaigns}")
        print(f"{'='*60}\n")


@app.route('/reports')
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

        # Get frequencies and formats for each campaign
        campaign_frequencies = {}
        for cid in campaign_ids:
            # Get frequency
            freq_key = f'frequency_{cid}'
            freq_value = request.form.get(freq_key, '4.0')
            try:
                campaign_frequencies[str(cid)] = float(freq_value)
            except ValueError:
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
            campaign_frequencies=campaign_frequencies,  # Frequency per campaign
            schedule_days=schedule_days,
            schedule_time=schedule_time,
            schedule_enabled=True,
            manager=manager
        )

        db.session.add(report)
        db.session.commit()

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

                # Get frequency for this campaign
                frequency = 3.0  # Default
                if report.campaign_frequencies and str(campaign.id) in report.campaign_frequencies:
                    frequency = report.campaign_frequencies[str(campaign.id)]

                campaigns_daily_data.append({
                    'campaign_id': campaign.campaign_id,
                    'campaign_name': campaign.name,
                    'format_type': campaign.format_type,  # Add format type (B/V/CTV/TGB)
                    'frequency': frequency,
                    'daily_data': daily_data
                })

                print(f"   ✅ Got {len(daily_data)} days of data (frequency: {frequency})")

            if not campaigns_daily_data:
                raise Exception("No data for any campaign in the period")

            # Write video detailed report to Google Sheets
            success = gs_client.write_video_detailed_data(
                sheet_url=report.google_sheet_url,
                sheet_name=report.worksheet_name,
                campaigns_daily_data=campaigns_daily_data
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

            for campaign in campaigns:
                # Get data for this campaign for entire period
                daily_data = sape_client.get_daily_stats(
                    campaign_ids=[int(campaign.campaign_id)],
                    date_from=date_from,
                    date_to=date_to,
                    include_video_metrics=(campaign.format_type == 'V')
                )

                if not daily_data:
                    print(f"⚠️  No data for campaign {campaign.campaign_id} ({campaign.name})")
                    continue

                # Sum all data for the period
                period_shows = sum(d['impressions'] for d in daily_data)
                period_clicks = sum(d['clicks'] for d in daily_data)

                # Get frequency for this campaign
                frequency = 3.0  # Default
                if report.campaign_frequencies and str(campaign.id) in report.campaign_frequencies:
                    frequency = report.campaign_frequencies[str(campaign.id)]

                print(f"✅ Campaign {campaign.campaign_id} ({campaign.name}):")
                print(f"   Shows: {period_shows:,}, Clicks: {period_clicks:,}")
                print(f"   Frequency target: {frequency}")

                campaigns_data.append({
                    'campaign_id': campaign.campaign_id,
                    'shows': period_shows,
                    'clicks': period_clicks,
                    'frequency': frequency
                })

                total_impressions += period_shows
                total_clicks += period_clicks

            if not campaigns_data:
                raise Exception("No data for any campaign in the period")

            # Write total report to Google Sheets
            success = gs_client.write_total_report_data(
                sheet_url=report.google_sheet_url,
                sheet_name=report.worksheet_name,
                campaigns_data=campaigns_data
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
            cached_worksheet_data = cached_worksheet_object.get('A1:DZ150')
            print(f"✅ Cached {len(cached_worksheet_data)} rows of data")
            # DEBUG: Check if data is empty
            if len(cached_worksheet_data) == 0:
                print(f"⚠️ WARNING: Cached worksheet data is EMPTY! This will cause ID detection to fail.")
                print(f"   Worksheet name might be incorrect or sheet might be empty.")
        else:
            print(f"⚠️ Failed to cache worksheet, will read individually (slower)")
            cached_worksheet_data = None

        for idx, campaign in enumerate(campaigns, 1):
            print(f"\n🔍 [{idx}/{len(campaigns)}] Searching for campaign {campaign.campaign_id} ({campaign.name})")

            # Minimal delay since we use cached data (no API calls during detection)
            # Small delay just to avoid overwhelming the system
            if idx > 1:
                import time
                time.sleep(0.1)  # 0.1 second - just to avoid overwhelming CPU

            # Detect structure for this campaign (using cached data for speed)
            structure = gs_client.auto_detect_structure(
                sheet_url=report.google_sheet_url,
                sheet_name=report.worksheet_name,  # Use worksheet from report config
                campaign_id=str(campaign.campaign_id),
                cached_data=cached_worksheet_data  # Pass cached data to avoid re-reading
            )

            if not structure:
                print(f"❌ Failed to detect structure for campaign {campaign.name} (ID: {campaign.campaign_id})")
                print(f"   Это означает что ID {campaign.campaign_id} не найден в заголовках листа '{report.worksheet_name}'")
                failed_campaign_ids.append(str(campaign.campaign_id))
                continue

            # Get campaign IDs from the detected header
            header_campaign_ids = structure.get('campaign_ids', [str(campaign.campaign_id)])
            section_key = frozenset(header_campaign_ids)

            if section_key not in sections_to_process:
                sections_to_process[section_key] = {
                    'structure': structure,
                    'campaigns': [],
                    'header_ids': header_campaign_ids
                }

            sections_to_process[section_key]['campaigns'].append(campaign)

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

                # Determine if any campaign in this section is video
                is_video = any(c.format_type == 'V' for c in section_campaigns)
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

                    # Calculate average frequency for combined campaigns
                    frequencies = []
                    for campaign_sape_id in header_ids:
                        campaign = campaigns_by_sape_id.get(campaign_sape_id)
                        if campaign and report.campaign_frequencies and str(campaign.id) in report.campaign_frequencies:
                            frequencies.append(report.campaign_frequencies[str(campaign.id)])
                        else:
                            frequencies.append(4.0)

                    avg_frequency = sum(frequencies) / len(frequencies) if frequencies else 4.0
                    print(f"📊 Using average frequency: {avg_frequency}")

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

                    # Get frequency for this campaign
                    avg_frequency = 4.0  # Default
                    if report.campaign_frequencies and str(campaign.id) in report.campaign_frequencies:
                        avg_frequency = report.campaign_frequencies[str(campaign.id)]
                    print(f"📊 Using frequency: {avg_frequency}")

                # Prepare column mapping
                column_mapping = {
                    'date_column': structure['date_column'],
                    'impressions_column': structure['impressions_column'],
                    'reach_column': structure['reach_column'],
                    'clicks_column': structure['clicks_column'],
                    'ctr_column': structure['ctr_column'],
                    'vast25_column': structure.get('vast25_column') if is_campaign_video else None,
                    'vast50_column': structure.get('vast50_column') if is_campaign_video else None,
                    'vast75_column': structure.get('vast75_column') if is_campaign_video else None,
                    'completes_column': structure.get('completes_column') if is_campaign_video else None
                }

                # Write data to Google Sheets (using cached worksheet to save API quota)
                print(f"🔍 DEBUG: About to write {len(daily_data_to_write)} days to Google Sheets...")
                success = gs_client.write_daily_data(
                    sheet_url=report.google_sheet_url,
                    sheet_name=report.worksheet_name,  # Use worksheet from report config
                    daily_data=daily_data_to_write,
                    column_mapping=column_mapping,
                    data_start_row=structure['data_start_row'],
                    frequency=avg_frequency,
                    frequency_variance=report.frequency_variance or 0.5,  # Use from config or default
                    total_reach_coefficient=report.total_reach_coefficient or 0.96,  # Use from config or default
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
        if google_sheet_url and google_sheet_url != report.google_sheet_url:
            report.google_sheet_url = google_sheet_url
            report.worksheet_name = worksheet_name

            # Re-detect structure if URL changed (skip for 'total' mode reports)
            # Total mode reports don't have "Показатели кампании" headers, so auto-detection won't work
            if report.campaign_mode != 'total':
                campaigns = Campaign.query.filter(Campaign.id.in_(report.campaign_ids)).all()
                if campaigns:
                    gs_client = GoogleSheetsClient(
                        credentials_file=app.config['GOOGLE_CREDENTIALS_FILE'],
                        scopes=app.config['GOOGLE_SCOPES']
                    )

                    first_campaign = campaigns[0]
                    structure = gs_client.auto_detect_structure(
                        sheet_url=google_sheet_url,
                        sheet_name=worksheet_name,  # Use selected worksheet
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

            # Update frequencies
            campaign_frequencies = {}
            for cid in campaign_ids:
                freq_key = f'frequency_{cid}'
                freq_value = request.form.get(freq_key, '4.0')
                try:
                    campaign_frequencies[str(cid)] = float(freq_value)
                except ValueError:
                    campaign_frequencies[str(cid)] = 3.0

                # Update format if changed
                format_key = f'format_{cid}'
                format_value = request.form.get(format_key)
                if format_value:
                    campaign = Campaign.query.get(cid)
                    if campaign:
                        campaign.format_type = format_value

            # Save campaign_frequencies (each campaign has its own frequency = max value)
            report.campaign_frequencies = campaign_frequencies

        # Process reach calculation settings (frequency_variance, total_reach_coefficient)
        frequency_variance = request.form.get('frequency_variance')
        total_reach_coefficient = request.form.get('total_reach_coefficient')

        app.logger.error(f"🔍 DEBUG: frequency_variance from form: '{frequency_variance}' (type: {type(frequency_variance)})")
        app.logger.error(f"🔍 DEBUG: Current report.frequency_variance: {report.frequency_variance}")

        if frequency_variance:
            try:
                variance = float(frequency_variance)
                app.logger.error(f"🔍 DEBUG: Parsed variance: {variance}")

                # Validate variance is in reasonable range
                if variance < 0:
                    flash('⚠️ Разброс частоты не может быть отрицательным!', 'warning')
                    variance = 0.5
                elif variance > 2.0:
                    flash('⚠️ Разброс частоты слишком большой (макс 2.0)!', 'warning')
                    variance = 2.0

                # Store frequency variance
                report.frequency_variance = variance

                app.logger.error(f"✅ Updated frequency variance: {variance}")

            except ValueError as e:
                flash(f'⚠️ Ошибка в настройках разброса: {e}', 'warning')
        else:
            app.logger.error(f"⚠️ WARNING: frequency_variance not in form or is empty!")

        if total_reach_coefficient:
            try:
                coeff = float(total_reach_coefficient)

                # Validate coefficient is in range [0.85, 0.99]
                if coeff < 0.85:
                    flash('⚠️ Коэффициент охвата не может быть меньше 0.85!', 'warning')
                    coeff = 0.85
                elif coeff >= 1.0:
                    flash('⚠️ Коэффициент охвата должен быть меньше 1.0!', 'warning')
                    coeff = 0.96

                report.total_reach_coefficient = coeff
                print(f"✅ Updated total reach coefficient: {coeff} ({int(coeff * 100)}%)")

            except ValueError as e:
                flash(f'⚠️ Ошибка в коэффициенте охвата: {e}', 'warning')

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
        campaign_frequencies=original_report.campaign_frequencies,
        frequency_variance=original_report.frequency_variance,
        total_reach_coefficient=original_report.total_reach_coefficient,
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


# ==================== DATABASE INITIALIZATION ====================

@app.cli.command()
def init_db():
    """Initialize database"""
    db.create_all()
    print("Database initialized!")


# ==================== SCHEDULER ====================

# Initialize and start scheduler only when running with Gunicorn
# Check if we're not in a Flask CLI context
import sys
if 'flask' not in sys.argv[0]:
    try:
        scheduler = BackgroundScheduler(timezone=pytz.timezone('Europe/Moscow'))

        # Add daily sync job at 00:00
        scheduler.add_job(
            func=scheduled_sync_all_accounts,
            trigger=CronTrigger(hour=0, minute=0),
            id='daily_sync_accounts',
            name='Синхронизация всех аккаунтов SAPE',
            replace_existing=True
        )

        # Start scheduler
        scheduler.start()
        print("✅ Scheduler started: Daily account sync at 00:00 Moscow time")
    except Exception as e:
        print(f"⚠️ Warning: Could not start scheduler: {e}")


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5006)
