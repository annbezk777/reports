"""
TargetAds (app.targetads.io) client - pulls daily impressions/clicks for
the SAPE-attributed slice of a project's traffic, to compare against our
own SAPE fact numbers (same idea as the Weborama verifier, but TargetAds
is plain HTTP - no headless browser needed).

Auth is a single org-wide login/password (clients share access, there's
no per-account credential), loaded once and reused across all monitorings
that use a TargetAds link.
"""
import os
import re
from datetime import datetime
from urllib.parse import unquote_plus

import requests


class TargetAdsFetchError(Exception):
    pass


class TargetAdsClient:
    BASE_URL = 'https://app.targetads.io/api'

    def __init__(self, email=None, password=None):
        self.email, self.password = (email, password) if email and password else self._load_credentials()
        self.access_token = None

    def _load_credentials(self):
        env_email = os.environ.get('TARGETADS_EMAIL')
        env_password = os.environ.get('TARGETADS_PASSWORD')
        if env_email and env_password:
            return env_email, env_password

        cred_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'targetads_credentials.txt'
        )
        email, password = None, None
        if os.path.exists(cred_path):
            with open(cred_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('TARGETADS_EMAIL='):
                        email = line.split('=', 1)[1].strip()
                    elif line.startswith('TARGETADS_PASSWORD='):
                        password = line.split('=', 1)[1].strip()
        return email, password

    def authenticate(self):
        if not self.email or not self.password:
            raise TargetAdsFetchError('TargetAds credentials не настроены (targetads_credentials.txt)')
        resp = requests.post(
            f'{self.BASE_URL}/auth/',
            json={'email': self.email, 'password': self.password},
            timeout=15
        )
        if resp.status_code != 200:
            raise TargetAdsFetchError(f'Не удалось авторизоваться в TargetAds: {resp.status_code} {resp.text}')
        self.access_token = resp.json()['access_token']
        return True

    @staticmethod
    def extract_project_id(url):
        """Pull the project id out of a TargetAds dashboard URL like
        https://app.targetads.io/#/projects/12775/?ps=...&pe=...&g=campaign"""
        if not url:
            return None
        match = re.search(r'/projects/(\d+)', url)
        return match.group(1) if match else None

    @staticmethod
    def extract_source_filter(url):
        """Pull the source filter's value list out of a TargetAds dashboard
        URL's `f=` param, e.g. ...&g=source&f=name%3Dsource%3Bcondition%3D
        equal%3Bvalue%3DSape+Geo+1%2CSape+Geo+2%2CSape+Geo+3 decodes to
        "name=source;condition=equal;value=Sape Geo 1,Sape Geo 2,Sape Geo 3".

        Not every project labels its SAPE-attributed traffic "Sape (FS)" -
        some split it into several source rows with project-specific names
        (e.g. "Sape Geo 1/2/3"). The only reliable way to get the right
        label(s) is from the exact URL the user copies after filtering by
        source to just the SAPE rows in the TargetAds UI - returns None if
        the URL doesn't carry that filter (older links), so the caller can
        fall back to the "Sape (FS)" default."""
        if not url:
            return None
        match = re.search(r'[?&]f=([^&]+)', url)
        if not match:
            return None
        decoded = unquote_plus(match.group(1))
        parts = dict(p.split('=', 1) for p in decoded.split(';') if '=' in p)
        if parts.get('name') != 'source' or not parts.get('value'):
            return None
        values = [v.strip() for v in parts['value'].split(',') if v.strip()]
        return values or None

    def _headers(self):
        return {'authorization': f'Bearer {self.access_token}', 'content-type': 'application/json'}

    def _fetch_dashboard(self, project_id, date_from, date_to, filter_body):
        body = {
            'common_params': {
                'interval_from': date_from.strftime('%Y-%m-%d'),
                'interval_to': date_to.strftime('%Y-%m-%d'),
                'simplify_values_type_names': True
            },
            'items': [
                {'name_id': 'media_main_chart_impressions', 'date_grouping': 'day', 'scale': 'day'},
                {'name_id': 'media_main_chart_click', 'date_grouping': 'day', 'scale': 'day'},
                {'name_id': 'media_table_chart_source', 'date_grouping': 'day', 'scale': 'day'},
            ],
            'filter': filter_body
        }
        resp = requests.post(
            f'{self.BASE_URL}/dashboard/fetch/?project_id={project_id}',
            headers=self._headers(),
            json=body,
            timeout=30
        )
        if resp.status_code != 200:
            raise TargetAdsFetchError(f'Ошибка запроса к TargetAds: {resp.status_code} {resp.text}')
        return resp.json()

    @staticmethod
    def _extract_stats(data):
        impressions_by_date = {
            row[0]: row[1] for row in data.get('media_main_chart_impressions', {}).get('data', {}).get('dataset', [])
        }
        clicks_by_date = {
            row[0]: row[1] for row in data.get('media_main_chart_click', {}).get('data', {}).get('dataset', [])
        }

        all_dates = sorted(set(impressions_by_date) | set(clicks_by_date))
        daily = [
            {
                'date_iso': d,
                'impressions': impressions_by_date.get(d, 0),
                'clicks': clicks_by_date.get(d, 0)
            }
            for d in all_dates
        ]

        # media_table_chart_source (ungrouped) returns one aggregate row for
        # the whole period with share_givt/share_sivt/share_ivt as 0-1
        # fractions - IVT quality metrics, not available per-day. Rounded to
        # 2 decimals to match the IVT/GIVT/SIVT form fields' step="0.01".
        ivt_shares = {'ivt_share': None, 'givt_share': None, 'sivt_share': None}
        table_rows = data.get('media_table_chart_source', {}).get('data', {}).get('dataset', [])
        table_cols = [c['name'] for c in data.get('media_table_chart_source', {}).get('data', {}).get('column', [])]
        if table_rows and table_cols:
            row = dict(zip(table_cols, table_rows[0]))
            if row.get('share_givt') is not None:
                ivt_shares['givt_share'] = round(row['share_givt'] * 100, 2)
            if row.get('share_sivt') is not None:
                ivt_shares['sivt_share'] = round(row['share_sivt'] * 100, 2)
            if row.get('share_ivt') is not None:
                ivt_shares['ivt_share'] = round(row['share_ivt'] * 100, 2)

        return daily, ivt_shares, table_rows, table_cols

    def get_daily_stats(self, project_id, date_from, date_to, source='Sape (FS)'):
        """
        Returns {'daily': [{'date_iso': ..., 'impressions': int, 'clicks': int}, ...],
                 'total_impressions': int, 'total_clicks': int}
        scoped to the given source(s) only - a string for one label, or a
        list for projects that split SAPE traffic across several source
        rows (e.g. "Sape Geo 1/2/3" - see extract_source_filter). Defaults
        to "Sape (FS)" for callers that don't have a more specific value
        parsed from the monitoring's own targetads_report_url.
        """
        if not self.access_token:
            self.authenticate()

        source_values = source if isinstance(source, list) else [source]
        data = self._fetch_dashboard(project_id, date_from, date_to, [{'name': 'source', 'condition': 'equal', 'value': source_values}])
        daily, ivt_shares, table_rows, table_cols = self._extract_stats(data)

        return {
            'daily': daily,
            'total_impressions': sum(r['impressions'] for r in daily),
            'total_clicks': sum(r['clicks'] for r in daily),
            **ivt_shares
        }
