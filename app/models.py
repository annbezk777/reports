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

    def get_campaigns(self):
        """Get list of Campaign objects for this report"""
        if not self.campaign_ids:
            return []
        return Campaign.query.filter(Campaign.id.in_(self.campaign_ids)).all()

    def get_asana_monitoring(self):
        """Find the monitoring whose Asana link should be shown on this
        report's card. Usually the directly-linked one (report_config_id),
        but a "total" monitoring spanning several reports' campaigns
        (e.g. one combined CTV monitoring covering two separate CTV_*
        reports) never gets a report_config_id of its own - fall back to
        an orphan monitoring whose campaign set fully contains this
        report's campaigns."""
        direct = next((m for m in self.monitoring_campaigns if m.asana_task_url), None)
        if direct:
            return direct

        if not self.campaign_ids:
            return None
        report_campaigns = set(self.campaign_ids)
        orphans = MonitoringCampaign.query.filter(
            MonitoringCampaign.report_config_id.is_(None),
            MonitoringCampaign.asana_task_url.isnot(None)
        ).all()
        for m in orphans:
            if m.campaign_ids and report_campaigns.issubset(set(m.campaign_ids)):
                return m
        return None

    def get_schedule_summary(self):
        """Короткое описание расписания автообновления для карточки -
        None, если автообновление выключено или дни не выбраны."""
        if not self.schedule_enabled or not self.schedule_days:
            return None
        day_names = {'1': 'Пн', '2': 'Вт', '3': 'Ср', '4': 'Чт', '5': 'Пт', '6': 'Сб', '7': 'Вс'}
        day_nums = [d for d in self.schedule_days.split(',') if d]
        days = [day_names.get(d, d) for d in day_nums]
        days_label = 'Пн-Вс' if len(day_nums) == 7 else ', '.join(days)
        time_label = self.schedule_time or '09:00'
        return f'{days_label} в {time_label}'


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


class MonitoringCampaign(db.Model):
    """Campaign monitoring with KPIs and targets"""
    __tablename__ = 'monitoring_campaigns'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)  # Название мониторинга

    # The report this monitoring was auto-created for (nullable - older
    # monitorings predate this link and some are created standalone)
    report_config_id = db.Column(db.Integer, db.ForeignKey('report_configs.id'), nullable=True)

    # Campaign references
    account_id = db.Column(db.Integer, db.ForeignKey('sape_accounts.id'), nullable=False)
    campaign_ids = db.Column(db.JSON, nullable=False)  # List of SAPE campaign IDs

    # Period
    date_from = db.Column(db.Date, nullable=False)
    date_to = db.Column(db.Date, nullable=False)

    # Media plan targets (SAPE statistics)
    plan_impressions = db.Column(db.Integer, nullable=True)  # Плановые показы
    plan_clicks = db.Column(db.Integer, nullable=True)  # Плановые клики

    # Post-click targets (Yandex Metrika)
    plan_visits = db.Column(db.Integer, nullable=True)  # Плановые визиты
    plan_conversions = db.Column(db.Integer, nullable=True)  # Плановые конверсии
    plan_bounce_rate = db.Column(db.Float, nullable=True)  # Плановый % отказов (например, 45.5)
    plan_time_on_site = db.Column(db.Float, nullable=True)  # Плановое время на сайте (сек.)
    plan_page_depth = db.Column(db.Float, nullable=True)  # Плановая глубина просмотра (стр.)
    plan_robotness = db.Column(db.Float, nullable=True)  # Плановая роботность (%)
    plan_pi = db.Column(db.Float, nullable=True)  # Плановый PI (%)
    plan_vtr = db.Column(db.Float, nullable=True)  # Плановый VTR (%)
    plan_ivt_impressions = db.Column(db.Float, nullable=True)  # IVT показы (%)
    plan_givt_impressions = db.Column(db.Float, nullable=True)  # GIVT показы (%)
    plan_sivt = db.Column(db.Float, nullable=True)  # SIVT (%)
    plan_givt_clicks = db.Column(db.Float, nullable=True)  # Клики GIVT (%)

    # Actual data (фактические данные за вчера)
    fact_impressions = db.Column(db.Integer, nullable=True)  # Фактические показы
    fact_clicks = db.Column(db.Integer, nullable=True)  # Фактические клики
    fact_visits = db.Column(db.Integer, nullable=True)  # Фактические визиты
    fact_bounce_rate = db.Column(db.Float, nullable=True)  # Фактический % отказов
    fact_time_on_site = db.Column(db.Float, nullable=True)  # Фактическое время на сайте (сек.)
    fact_page_depth = db.Column(db.Float, nullable=True)  # Фактическая глубина просмотра
    fact_robotness = db.Column(db.Float, nullable=True)  # Фактическая роботность (%)
    fact_ivt_impressions = db.Column(db.Float, nullable=True)  # Фактический IVT показы (%)
    fact_givt_impressions = db.Column(db.Float, nullable=True)  # Фактический GIVT показы (%)
    fact_sivt_impressions = db.Column(db.Float, nullable=True)  # Фактический SIVT показы (%)
    fact_givt_clicks = db.Column(db.Float, nullable=True)  # Фактический GIVT клики (%)
    fact_vtr = db.Column(db.Float, nullable=True)  # Фактический VTR (%)

    # Сырые показы/клики из Adriver - для сверки расхождений с SAPE (не очищенные от IVT)
    adriver_impressions = db.Column(db.Integer, nullable=True)
    adriver_clicks = db.Column(db.Integer, nullable=True)

    # Yandex Metrika settings
    metrika_counter_id = db.Column(db.String(50), nullable=True)  # Номер счетчика Метрики
    metrika_goal_id = db.Column(db.String(50), nullable=True)  # ID цели для конверсий
    utm_source = db.Column(db.String(100), nullable=True)  # UTM метка для фильтрации
    utm_campaign = db.Column(db.String(100), nullable=True)  # UTM метка для фильтрации

    # Manager & metadata
    manager = db.Column(db.String(100), nullable=True)
    google_sheet_url = db.Column(db.String(500), nullable=True)  # Ссылка на Google таблицу
    asana_task_url = db.Column(db.String(500), nullable=True)  # Ссылка на задачу Asana
    asana_kpi_comment = db.Column(db.Text, nullable=True)  # Комментарий из поля KPI задачи Asana

    # Status
    active = db.Column(db.Boolean, default=True)
    archived = db.Column(db.Boolean, default=False)
    last_sync = db.Column(db.DateTime, nullable=True)  # Последнее обновление данных
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    account = db.relationship('SapeAccount', backref='monitoring_campaigns', lazy=True)
    report_config = db.relationship('ReportConfig', backref='monitoring_campaigns', lazy=True)

    def __repr__(self):
        return f'<MonitoringCampaign {self.name}>'

    def get_campaigns(self):
        """Get list of Campaign objects for this monitoring"""
        if not self.campaign_ids:
            return []
        return Campaign.query.filter(Campaign.id.in_(self.campaign_ids)).all()

    def get_total_days(self):
        """Calculate total days in monitoring period"""
        if not self.date_from or not self.date_to:
            return 0
        delta = self.date_to - self.date_from
        return delta.days + 1  # Include both start and end dates

    def get_days_left(self):
        """Calculate days left until monitoring end date"""
        if not self.date_to:
            return 0
        from datetime import datetime
        today = datetime.now().date()
        delta = self.date_to - today
        return max(0, delta.days)  # Don't return negative values

    def get_days_passed_until_yesterday(self):
        """Calculate days passed from start until yesterday (for stats)"""
        if not self.date_from:
            return 0
        from datetime import datetime, timedelta
        yesterday = datetime.now().date() - timedelta(days=1)

        # If campaign hasn't started yet
        if yesterday < self.date_from:
            return 0

        # If campaign has ended
        if self.date_to and yesterday > self.date_to:
            return self.get_total_days()

        # Normal case: count from start to yesterday
        delta = yesterday - self.date_from
        return delta.days + 1  # Include both start and yesterday

    def get_uniform_performance_percent(self, fact_value, plan_value):
        """
        Calculate performance percentage with uniform daily distribution

        Formula: (Fact / Expected_plan_for_passed_days) * 100%
        Where: Expected_plan = (Total_plan / Total_days) * Days_passed_until_yesterday

        Args:
            fact_value: Actual value (for yesterday)
            plan_value: Total planned value for entire campaign

        Returns:
            Performance percentage or None
        """
        if not fact_value or not plan_value or plan_value == 0:
            return None

        total_days = self.get_total_days()
        days_passed = self.get_days_passed_until_yesterday()

        if total_days == 0 or days_passed == 0:
            return None

        # Expected plan for the days that have passed
        expected_plan = (plan_value / total_days) * days_passed

        if expected_plan == 0:
            return None

        # Performance percentage
        return round((fact_value / expected_plan) * 100, 1)

    def get_fact_pi(self):
        """Calculate actual PI (Passing Index) from visits and clicks"""
        if self.fact_clicks and self.fact_clicks > 0 and self.fact_visits:
            return round((self.fact_visits / self.fact_clicks) * 100, 2)
        return None

    def get_fact_ctr(self):
        """Calculate actual CTR (Click-Through Rate) from clicks and impressions"""
        if self.fact_impressions and self.fact_impressions > 0 and self.fact_clicks:
            return round((self.fact_clicks / self.fact_impressions) * 100, 2)
        return None

    def get_plan_ctr(self):
        """Calculate planned CTR from plan clicks and impressions"""
        if self.plan_impressions and self.plan_impressions > 0 and self.plan_clicks:
            return round((self.plan_clicks / self.plan_impressions) * 100, 2)
        return None

    def is_video_format(self):
        """Check if monitoring campaigns are video format (V or CTV)"""
        campaigns = self.get_campaigns()
        if not campaigns:
            return False
        # If any campaign is video format (V or CTV), treat as video
        return any(c.format_type in ('V', 'CTV') for c in campaigns)

    def get_format_label(self):
        """Get VTR for video or VR for banners/TGB"""
        return 'VTR' if self.is_video_format() else 'VR'

    def get_fact_vr(self):
        """Get actual VTR (Video Through Rate) for video formats or VR for banners"""
        return self.fact_vtr

    def get_plan_vr(self):
        """Get planned VTR (Video Through Rate) for video formats or VR for banners"""
        return self.plan_vtr

    def get_performance_percent(self, fact_value, plan_value, inverse=False):
        """
        Calculate performance percentage

        Args:
            fact_value: Actual value
            plan_value: Planned value
            inverse: If True, better when fact < plan (for bounce rate, robotness, etc.)

        Returns:
            Performance percentage or None
        """
        if not fact_value or not plan_value or plan_value == 0:
            return None

        if inverse:
            # For metrics where lower is better (bounce rate, robotness, IVT)
            # If fact < plan, that's good (>100%)
            # If fact > plan, that's bad (<100%)
            return round((plan_value / fact_value) * 100, 1)
        else:
            # For metrics where higher is better (impressions, clicks, visits, etc.)
            return round((fact_value / plan_value) * 100, 1)

    def get_visits_diff_percent(self):
        """Визиты: показать разницу в процентах (+26%)"""
        if not self.fact_visits or not self.plan_visits or self.plan_visits == 0:
            return None
        diff_percent = ((self.fact_visits - self.plan_visits) / self.plan_visits) * 100
        return round(diff_percent, 1)

    def get_bounce_diff(self):
        """Отказы: показать разницу со знаком < или > (<5.6 или >5.6)"""
        if self.fact_bounce_rate is None or not self.plan_bounce_rate:
            return None
        diff = self.fact_bounce_rate - self.plan_bounce_rate
        return round(diff, 1)

    def get_time_diff_seconds(self):
        """Время: показать разницу в секундах (+15с или -15с)"""
        if self.fact_time_on_site is None or not self.plan_time_on_site:
            return None
        diff = self.fact_time_on_site - self.plan_time_on_site
        return round(diff, 0)

    def get_depth_diff(self):
        """Глубина: показать разницу со знаком < или > (<0.4 или >0.4)"""
        if self.fact_page_depth is None or not self.plan_page_depth:
            return None
        diff = self.fact_page_depth - self.plan_page_depth
        return round(diff, 1)

    def get_robotness_diff(self):
        """Роботность: показать разницу (-6.8 или +6.8)"""
        if self.fact_robotness is None or not self.plan_robotness:
            return None
        diff = self.fact_robotness - self.plan_robotness
        return round(diff, 1)

    def get_pi_diff_percent(self):
        """PI: показать разницу в процентах (>25% или <25%)"""
        fact_pi = self.get_fact_pi()
        if fact_pi is None or not self.plan_pi:
            return None
        diff = fact_pi - self.plan_pi
        return round(diff, 1)

    def get_ivt_diff(self):
        """IVT: разница факта с плановым порогом (план - это "не более X%")"""
        if not self.fact_ivt_impressions or not self.plan_ivt_impressions:
            return None
        return round(self.fact_ivt_impressions - self.plan_ivt_impressions, 2)

    def get_givt_diff(self):
        if not self.fact_givt_impressions or not self.plan_givt_impressions:
            return None
        return round(self.fact_givt_impressions - self.plan_givt_impressions, 2)

    def get_sivt_diff(self):
        if not self.fact_sivt_impressions or not self.plan_sivt:
            return None
        return round(self.fact_sivt_impressions - self.plan_sivt, 2)

    def get_givt_clicks_diff(self):
        if not self.fact_givt_clicks or not self.plan_givt_clicks:
            return None
        return round(self.fact_givt_clicks - self.plan_givt_clicks, 2)

    def get_ctr_diff(self):
        """CTR: показать разницу (+0.06 или -0.06)"""
        fact_ctr = self.get_fact_ctr()
        plan_ctr = self.get_plan_ctr()
        if fact_ctr is None or plan_ctr is None:
            return None
        diff = fact_ctr - plan_ctr
        return round(diff, 2)

    def get_vtr_diff(self):
        """VTR: показать разницу (+11 или -9)"""
        if self.fact_vtr is None or not self.plan_vtr:
            return None
        diff = self.fact_vtr - self.plan_vtr
        return round(diff, 0)

    def get_daily_limit_impressions(self):
        """Calculate daily impressions limit (evenly distributed)"""
        days = self.get_total_days()
        if days > 0 and self.plan_impressions:
            return int(self.plan_impressions / days)
        return 0

    def get_daily_limit_clicks(self):
        """Calculate daily clicks limit (evenly distributed)"""
        days = self.get_total_days()
        if days > 0 and self.plan_clicks:
            return int(self.plan_clicks / days)
        return 0

    def get_adriver_impressions_diff_percent(self):
        """% = (Adriver − SAPE) / Adriver × 100 - отрицательное значение,
        когда у нас в платформе (SAPE) показов больше, чем у верификатора.
        Делитель (Adriver) обязан быть ненулевым - делить на 0 нельзя. А
        вот SAPE-факт, равный ровно 0, валиден и не должен блокировать
        расчёт (поэтому is None, а не truthy-проверка)."""
        if not self.adriver_impressions or not self.fact_impressions:
            return None
        return round((self.adriver_impressions - self.fact_impressions) / self.adriver_impressions * 100, 1)

    def get_adriver_clicks_diff_percent(self):
        """% = (SAPE − Adriver) / Adriver × 100 - для кликов знак не
        инвертируется, в отличие от показов (см. get_adriver_impressions_diff_percent)."""
        if not self.adriver_clicks or not self.fact_clicks:
            return None
        return round((self.fact_clicks - self.adriver_clicks) / self.adriver_clicks * 100, 1)

    def get_weborama_impressions(self):
        """Sum of показы across every Weborama mapping on this monitoring -
        a monitoring can have several insertions (banner+video from one
        permalink, or several permalinks), so the table-level summary is
        their total, not any single mapping's value."""
        total = 0
        found = False
        for link in self.verifier_links:
            if link.verifier_type != 'weborama':
                continue
            for mapping in link.mappings:
                if mapping.verifier_impressions:
                    total += mapping.verifier_impressions
                    found = True
        return total if found else None

    def get_weborama_clicks(self):
        total = 0
        found = False
        for link in self.verifier_links:
            if link.verifier_type != 'weborama':
                continue
            for mapping in link.mappings:
                if mapping.verifier_clicks:
                    total += mapping.verifier_clicks
                    found = True
        return total if found else None

    def _weborama_mappings(self):
        return [
            m for link in self.verifier_links if link.verifier_type == 'weborama'
            for m in link.mappings
        ]

    def _distinct_weborama_sape_fact_mappings(self):
        """Weborama mappings, de-duplicated by their exact campaign set -
        when several mappings cover the SAME group of campaigns (one
        Weborama pixel split into multiple Insertion rows that all share
        the same underlying SAPE campaigns, e.g. two ad creatives running
        across the same 7 campaigns), each mapping's sape_fact_* is
        already the FULL total for that whole group, not a per-row
        slice of it - summing every mapping would double/triple-count
        the SAPE side. Keep only one representative mapping per distinct
        campaign set so each group's fact is counted exactly once."""
        seen = set()
        result = []
        for m in self._weborama_mappings():
            key = frozenset(m.campaign_ids_list())
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(m)
        return result

    def get_weborama_sape_fact_impressions(self):
        """Sum of the per-campaign-group SAPE fact for exactly the
        campaigns that have a Weborama mapping - NOT the whole
        monitoring's combined fact, which may include other campaigns
        the permalink doesn't cover. Falls back to the mapping's own
        fallback (monitoring total) for any mapping that hasn't been
        refreshed with per-campaign data yet."""
        total = 0
        found = False
        for m in self._distinct_weborama_sape_fact_mappings():
            sape_imp, _ = m._sape_facts()
            if sape_imp:
                total += sape_imp
                found = True
        return total if found else None

    def get_weborama_sape_fact_clicks(self):
        total = 0
        found = False
        for m in self._distinct_weborama_sape_fact_mappings():
            _, sape_clk = m._sape_facts()
            if sape_clk:
                total += sape_clk
                found = True
        return total if found else None

    def get_weborama_impressions_diff_percent(self):
        """% = (Weborama − SAPE) / Weborama × 100, scoped to just the
        mapped campaigns' own SAPE fact (see get_weborama_sape_fact_impressions).
        Negative when SAPE shows more than Weborama (sign intentionally
        flipped vs. clicks - see get_weborama_clicks_diff_percent).
        Делитель (Weborama) обязан быть ненулевым, но SAPE-факт, равный
        ровно 0, валиден и не должен блокировать расчёт."""
        imp = self.get_weborama_impressions()
        sape_fact = self.get_weborama_sape_fact_impressions()
        if not imp or not sape_fact:
            return None
        return round((imp - sape_fact) / imp * 100, 1)

    def get_weborama_clicks_diff_percent(self):
        """% = (SAPE − Weborama) / Weborama × 100 - sign NOT flipped here,
        unlike impressions (see get_weborama_impressions_diff_percent)."""
        clk = self.get_weborama_clicks()
        sape_fact = self.get_weborama_sape_fact_clicks()
        if not clk or not sape_fact:
            return None
        return round((sape_fact - clk) / clk * 100, 1)


class VerifierLink(db.Model):
    """A verifier (Weborama/Adriver) permalink attached to a monitoring.

    One permalink can cover several SAPE campaigns at once (e.g. one
    Weborama campaign with a "Sape_Banner_X" and a "Sape_Video_X"
    insertion) - see VerifierLinkMapping for the per-campaign numbers.
    """
    __tablename__ = 'verifier_links'

    id = db.Column(db.Integer, primary_key=True)
    monitoring_id = db.Column(db.Integer, db.ForeignKey('monitoring_campaigns.id'), nullable=False)

    verifier_type = db.Column(db.String(20), nullable=False)  # 'weborama' | 'adriver'
    label = db.Column(db.String(100), nullable=True)  # Направление, например "Особый"
    permalink_url = db.Column(db.String(1000), nullable=True)

    # Устаревшие поля одиночного сопоставления (до перехода на
    # VerifierLinkMapping) - оставлены в схеме для совместимости со старыми
    # строками, новым кодом не используются.
    insertion_name = db.Column(db.String(200), nullable=True)
    sape_campaign_ids = db.Column(db.JSON, nullable=True)
    verifier_impressions = db.Column(db.Integer, nullable=True)
    verifier_clicks = db.Column(db.Integer, nullable=True)

    # Из Excel-выгрузки Adriver (сырые числа, не только %)
    ivt_impressions = db.Column(db.Integer, nullable=True)
    ivt_impressions_percent = db.Column(db.Float, nullable=True)
    givt_impressions = db.Column(db.Integer, nullable=True)
    givt_impressions_percent = db.Column(db.Float, nullable=True)
    sivt_impressions = db.Column(db.Integer, nullable=True)
    sivt_impressions_percent = db.Column(db.Float, nullable=True)
    ivt_clicks = db.Column(db.Integer, nullable=True)
    ivt_clicks_percent = db.Column(db.Float, nullable=True)
    givt_clicks = db.Column(db.Integer, nullable=True)
    givt_clicks_percent = db.Column(db.Float, nullable=True)
    sivt_clicks = db.Column(db.Integer, nullable=True)
    sivt_clicks_percent = db.Column(db.Float, nullable=True)

    last_fetched_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    monitoring = db.relationship('MonitoringCampaign', backref=db.backref('verifier_links', cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<VerifierLink {self.verifier_type}:{self.label or self.id}>'


class VerifierLinkMapping(db.Model):
    """One (SAPE campaign, Weborama Insertion) pairing under a permalink.

    A single Weborama permalink's Insertions table can hold several rows
    (e.g. one per ad format) - each gets its own mapping here so every
    campaign's показы/клики are tracked and compared independently,
    without re-fetching the same permalink once per campaign.
    """
    __tablename__ = 'verifier_link_mappings'

    id = db.Column(db.Integer, primary_key=True)
    verifier_link_id = db.Column(db.Integer, db.ForeignKey('verifier_links.id'), nullable=False)

    sape_campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=True)
    # Когда один Weborama-пиксель/Insertion покрывает сразу НЕСКОЛЬКО SAPE-кампаний
    # (одна общая цифра у верификатора на всех) - список Campaign.id, SAPE-факт
    # суммируется по всем сразу. Если задан, имеет приоритет над sape_campaign_id
    # (который остаётся для старых однокампанийных маппингов).
    sape_campaign_ids = db.Column(db.JSON, nullable=True)
    insertion_name = db.Column(db.String(200), nullable=True)  # Точное название Insertion в Weborama (напр. "Sape_Banner_Lyovushka")

    verifier_impressions = db.Column(db.Integer, nullable=True)
    verifier_clicks = db.Column(db.Integer, nullable=True)
    last_fetched_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # SAPE fact показы/клики for THIS mapping's own campaign only (not the
    # whole monitoring - a monitoring can bundle several campaigns and the
    # verifier permalink usually only covers one of them). Fetched via a
    # separate per-campaign SAPE API call each time the monitoring is
    # refreshed - see _refresh_verifier_campaign_facts() in app.py.
    sape_fact_impressions = db.Column(db.Integer, nullable=True)
    sape_fact_clicks = db.Column(db.Integer, nullable=True)
    sape_fact_updated_at = db.Column(db.DateTime, nullable=True)

    verifier_link = db.relationship('VerifierLink', backref=db.backref('mappings', cascade='all, delete-orphan'))
    campaign = db.relationship('Campaign')

    def __repr__(self):
        return f'<VerifierLinkMapping {self.insertion_name or self.id}>'

    def campaign_ids_list(self):
        """Effective list of SAPE campaign (Campaign.id) PKs covered by
        this mapping's one verifier number."""
        if self.sape_campaign_ids:
            return list(self.sape_campaign_ids)
        if self.sape_campaign_id:
            return [self.sape_campaign_id]
        return []

    def _sape_facts(self):
        """Показы/клики SAPE для сравнения - предпочитаем факт по самой
        этой кампании (sape_fact_*, см. выше); до первого обновления
        мониторинга после появления этого поля откатываемся на агрегат
        по всему мониторингу (менее точно, если в мониторинге несколько
        кампаний)."""
        if self.sape_fact_impressions is not None or self.sape_fact_clicks is not None:
            return self.sape_fact_impressions, self.sape_fact_clicks
        monitoring = self.verifier_link.monitoring
        return monitoring.fact_impressions, monitoring.fact_clicks

    def get_impressions_diff_percent(self):
        """% = (SAPE − верификатор) / верификатор × 100"""
        sape_impressions, _ = self._sape_facts()
        if not self.verifier_impressions or not sape_impressions:
            return None
        return round((sape_impressions - self.verifier_impressions) / self.verifier_impressions * 100, 1)

    def get_clicks_diff_percent(self):
        """% = (SAPE − верификатор) / верификатор × 100"""
        _, sape_clicks = self._sape_facts()
        if not self.verifier_clicks or not sape_clicks:
            return None
        return round((sape_clicks - self.verifier_clicks) / self.verifier_clicks * 100, 1)
