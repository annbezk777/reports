"""
Asana API client for pulling media-plan target fields into monitoring.

Reads a fixed set of custom fields from a task and maps them onto
MonitoringCampaign's plan_* columns. Fields that hold per-format values
(показы, клики, CTR) are stored as "видео;баннеры;натив" - the active
slot is picked based on the task's own "Формат" field.
"""
import os
import re
from datetime import datetime

import requests

FORMAT_ORDER = ['видео', 'баннеры', 'натив']  # index 0/1/2; "натив" covers ТГБ


class AsanaClient:
    BASE_URL = 'https://app.asana.com/api/1.0'

    def __init__(self, token=None):
        self.token = token or self._load_token()

    def _load_token(self):
        env_token = os.environ.get('ASANA_PERSONAL_ACCESS_TOKEN')
        if env_token:
            return env_token

        cred_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'asana_credentials.txt'
        )
        if os.path.exists(cred_path):
            with open(cred_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('ASANA_PERSONAL_ACCESS_TOKEN='):
                        return line.split('=', 1)[1].strip()
        return None

    @staticmethod
    def extract_task_gid(url):
        """Pull the task GID out of an app.asana.com task URL"""
        if not url:
            return None
        match = re.search(r'/task/(\d+)', url)
        return match.group(1) if match else None

    def get_task(self, task_gid):
        if not self.token:
            raise RuntimeError('Asana token is not configured')

        resp = requests.get(
            f'{self.BASE_URL}/tasks/{task_gid}',
            headers={'Authorization': f'Bearer {self.token}'},
            params={
                'opt_fields': 'name,notes,custom_fields.name,custom_fields.type,'
                              'custom_fields.text_value,custom_fields.display_value,'
                              'custom_fields.date_value.date,'
                              'custom_fields.multi_enum_values.name'
            },
            timeout=20
        )
        resp.raise_for_status()
        return resp.json()['data']

    @staticmethod
    def _field_text(field):
        if not field:
            return None
        return field.get('text_value') if field.get('text_value') is not None else field.get('display_value')

    @staticmethod
    def _parse_date(raw):
        if not raw:
            return None
        try:
            return datetime.strptime(raw[:10], '%Y-%m-%d').date()
        except ValueError:
            return None

    @staticmethod
    def _notes_field(notes, label_pattern):
        """Pull the value following a 'Label:' line out of a task's free-text
        notes - some intake forms (e.g. the DSP launch form) put the account
        manager's contact info and the stats-sheet link there as plain text
        ("Имя:\n\nVladislav Fesenko"), not as a custom_field. Works whether
        the value sits on the same line as the label or the next one."""
        if not notes:
            return None
        match = re.search(rf'{label_pattern}\s*:\s*\n*\s*(.+)', notes, re.IGNORECASE)
        return match.group(1).strip() if match else None

    # Letter badge shown on report/monitoring cards for the verifier named
    # in a task's free-text "Верификатор:" line. Checked in order, first
    # match wins - order matters only for "target ads" vs a stray "ads".
    VERIFIER_BADGES = [
        (r'weborama|веборама', 'W'),
        (r'adservin|sizmek|сайзмек|адсервин', 'S'),
        (r'target\s*ads|таргет\s*(эдс|адс)', 'T'),
        (r'adriver|адривер', 'A'),
    ]

    @classmethod
    def _detect_verifier_badge(cls, raw):
        if not raw:
            return None
        text = raw.lower()
        for pattern, letter in cls.VERIFIER_BADGES:
            if re.search(pattern, text):
                return letter
        return None

    @classmethod
    def parse_task_notes(cls, notes):
        """Extract the account-manager contact, stats-sheet link,
        Metrika counter, and verifier badge from a task's free-text
        notes block, when present."""
        if not notes:
            return {}

        email_raw = cls._notes_field(notes, r'Адрес электронной почты')
        email = None
        if email_raw:
            m = re.search(r'[\w.+-]+@[\w.-]+\.\w+', email_raw)
            email = m.group(0).lower() if m else None

        sheet_raw = cls._notes_field(notes, r'Ссылка на статистический отчет')
        sheet_url = None
        if sheet_raw:
            m = re.search(r'https?://\S+', sheet_raw)
            sheet_url = m.group(0) if m else None

        result = {
            'account_manager_email': email,
            'account_manager_name': cls._notes_field(notes, r'Имя'),
            'google_sheet_url': sheet_url,
            'metrika_counter_id': cls._notes_field(notes, r'#\s*счетчика'),
            'verifier_badge': cls._detect_verifier_badge(cls._notes_field(notes, r'Верификатор')),
        }
        return {k: v for k, v in result.items() if v}

    @classmethod
    def _detect_format_index(cls, format_field):
        if not format_field:
            return None

        selected = []
        multi = format_field.get('multi_enum_values') or []
        if multi:
            selected = [v['name'].strip().lower() for v in multi if v.get('name')]
        elif format_field.get('display_value'):
            selected = [format_field['display_value'].strip().lower()]

        for name in selected:
            if 'видео' in name:
                return 0
            if 'баннер' in name:
                return 1
            if 'натив' in name or 'тгб' in name:
                return 2
        return None

    @staticmethod
    def prorate_to_period(total, task_date_from, task_date_to, period_from, period_to):
        """Distribute a total that covers [task_date_from, task_date_to]
        evenly across days, and return the portion that falls inside
        [period_from, period_to]. Used when an Asana task's media plan
        spans several months but a monitoring only tracks one of them."""
        task_days = (task_date_to - task_date_from).days + 1
        if task_days <= 0:
            return total
        overlap_start = max(task_date_from, period_from)
        overlap_end = min(task_date_to, period_to)
        overlap_days = (overlap_end - overlap_start).days + 1
        if overlap_days <= 0:
            return 0
        if overlap_days >= task_days:
            return total
        return total * overlap_days / task_days

    @staticmethod
    def format_index_for_campaign_type(format_type):
        """Map a SAPE campaign format_type (V/CTV/B/TGB) to the Asana
        показы/клики slot index (0=видео, 1=баннеры, 2=натив/ТГБ)."""
        if format_type in ('V', 'CTV'):
            return 0
        if format_type == 'TGB':
            return 2
        return 1  # B (banner) and anything else

    @classmethod
    def parse_monitoring_fields(cls, task_data, format_idx=None):
        """
        Map a task's custom fields onto monitoring plan_* values.
        Returns a dict with whatever fields were successfully parsed;
        missing/unparseable fields are simply omitted.

        format_idx: which slot (0=видео, 1=баннеры, 2=натив/ТГБ) to read
        from the semicolon-separated показы/клики/CTR fields. Pass this
        explicitly based on the *monitoring's own* format (derived from
        its SAPE campaigns) rather than trusting the task's own "Формат"
        field - a task can have multiple formats selected (in which case
        several monitorings share one task, each reading its own slot),
        and the task's Формат field is manually filled and can be wrong.
        If not passed, falls back to auto-detecting from the task's
        Формат field (used only for display / when no monitoring context
        is available).
        """
        fields_by_name = {}
        for f in task_data.get('custom_fields', []):
            name = (f.get('name') or '').strip().lower()
            if name:
                fields_by_name[name] = f

        format_field = fields_by_name.get('формат')
        if format_idx is None:
            format_idx = cls._detect_format_index(format_field)

        def list_value(key):
            raw = cls._field_text(fields_by_name.get(key))
            if raw is None or format_idx is None:
                return None
            parts = [p.strip() for p in str(raw).split(';')]
            if format_idx >= len(parts):
                return None
            try:
                return float(parts[format_idx].replace(',', '.'))
            except ValueError:
                return None

        def single_value(key):
            raw = cls._field_text(fields_by_name.get(key))
            if raw is None:
                return None
            raw = str(raw).strip()
            if raw in ('', '-'):
                return None
            try:
                return float(raw.replace(',', '.'))
            except ValueError:
                return None

        def text_value(key):
            raw = cls._field_text(fields_by_name.get(key))
            if raw is None:
                return None
            raw = str(raw).strip()
            return raw if raw and raw != '-' else None

        def date_value(key):
            field = fields_by_name.get(key)
            if not field:
                return None
            date_field = field.get('date_value')
            raw = date_field.get('date') if date_field else None
            return cls._parse_date(raw or cls._field_text(field))

        result = {
            'task_name': task_data.get('name'),
            'format': format_field.get('display_value') if format_field else None,
            'impressions': list_value('показы'),
            'clicks': list_value('клики'),
            'vtr': single_value('vtr'),
            'pi': single_value('pi'),
            'bounce': single_value('отказы'),
            'time': single_value('время'),
            'depth': single_value('глубина'),
            'robotness': single_value('роботность'),
            'kpi_comment': text_value('kpi'),
            'task_date_from': date_value('дата старта'),
            'task_date_to': date_value('дата завершения'),
        }
        return {k: v for k, v in result.items() if v is not None}
