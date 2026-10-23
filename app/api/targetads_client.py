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

    def _headers(self):
        return {'authorization': f'Bearer {self.access_token}', 'content-type': 'application/json'}

    def get_daily_stats(self, project_id, date_from, date_to, source='Sape (FS)'):
        """
        Returns {'daily': [{'date_iso': ..., 'impressions': int, 'clicks': int}, ...],
                 'total_impressions': int, 'total_clicks': int}
        scoped to the given source only (default: just the SAPE-attributed slice).
        """
        if not self.access_token:
            self.authenticate()

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
            'filter': [{'name': 'source', 'condition': 'equal', 'value': [source]}]
        }

        resp = requests.post(
            f'{self.BASE_URL}/dashboard/fetch/?project_id={project_id}',
            headers=self._headers(),
            json=body,
            timeout=30
        )
        if resp.status_code != 200:
            raise TargetAdsFetchError(f'Ошибка запроса к TargetAds: {resp.status_code} {resp.text}')

        data = resp.json()
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
        # fractions - IVT quality metrics, not available per-day.
        ivt_shares = {'ivt_share': None, 'givt_share': None, 'sivt_share': None}
        table = data.get('media_table_chart_source', {}).get('data', {})
        rows = table.get('dataset', [])
        cols = [c['name'] for c in table.get('column', [])]
        if rows and cols:
            row = dict(zip(cols, rows[0]))
            if row.get('share_givt') is not None:
                ivt_shares['givt_share'] = round(row['share_givt'] * 100, 2)
            if row.get('share_sivt') is not None:
                ivt_shares['sivt_share'] = round(row['share_sivt'] * 100, 2)
            if row.get('share_ivt') is not None:
                ivt_shares['ivt_share'] = round(row['share_ivt'] * 100, 2)

        return {
            'daily': daily,
            'total_impressions': sum(r['impressions'] for r in daily),
            'total_clicks': sum(r['clicks'] for r in daily),
            **ivt_shares
        }
