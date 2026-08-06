import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional


class SapeAPIClient:
    """Client for SAPE Traffic REST API"""

    def __init__(self, login: str, token: str):
        self.login = login
        self.token = token
        self.api_url = 'https://traffic.sape.ru/api/v2'
        self.access_token = None

    def authenticate(self) -> bool:
        """
        Authenticate with SAPE API using login and token

        Returns:
            bool: True if authentication successful
        """
        try:
            response = requests.post(
                f"{self.api_url}/login",
                json={
                    "login": self.login,
                    "token": self.token
                },
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get('accessToken')
                print(f"✅ SAPE authentication successful. Access token received.")
                return True
            else:
                print(f"❌ SAPE authentication failed: {response.status_code}")
                return False

        except Exception as e:
            print(f"SAPE authentication error: {e}")
            return False

    def _get_headers(self) -> Dict:
        """Get headers with access token"""
        if not self.access_token:
            raise Exception("Not authenticated. Please call authenticate() first.")

        return {
            "Authorization": self.access_token,
            "Content-Type": "application/json"
        }

    def get_campaigns(self) -> Optional[List[Dict]]:
        """
        Get list of user's campaigns

        Returns:
            list: List of campaigns with their IDs and names
        """
        if not self.access_token:
            if not self.authenticate():
                return None

        try:
            response = requests.get(
                f"{self.api_url}/campaigns/list",
                headers={"Authorization": self.access_token},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                campaigns = data.get('campaigns', [])

                # DEBUG: Print full campaign structure to check for client_id
                if campaigns and len(campaigns) > 0:
                    print(f"📋 DEBUG: Sample campaign structure:")
                    print(f"   Keys: {campaigns[0].keys()}")
                    print(f"   Full data: {campaigns[0]}")

                return campaigns
            else:
                print(f"Error getting campaigns: {response.status_code}")
                return None

        except Exception as e:
            print(f"Error getting campaigns: {e}")
            return None

    def get_campaign_detail(self, campaign_id: int) -> Optional[Dict]:
        """
        Get detailed campaign information including clientId

        Args:
            campaign_id: Campaign ID

        Returns:
            dict: Detailed campaign data with clientId
        """
        if not self.access_token:
            if not self.authenticate():
                return None

        try:
            response = requests.get(
                f"{self.api_url}/campaign/{campaign_id}",
                headers={"Authorization": self.access_token},
                timeout=10
            )

            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error getting campaign detail: {response.status_code}")
                return None

        except Exception as e:
            print(f"Error getting campaign detail: {e}")
            return None

    def get_clients(self) -> Optional[List[Dict]]:
        """
        Get list of clients

        Returns:
            list: List of clients
        """
        if not self.access_token:
            if not self.authenticate():
                return None

        try:
            response = requests.get(
                f"{self.api_url}/clients/list",
                headers={"Authorization": self.access_token},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                return data.get('clients', [])
            else:
                print(f"Error getting clients: {response.status_code}")
                return None

        except Exception as e:
            print(f"Error getting clients: {e}")
            return None

    def get_stats(
        self,
        campaign_ids: List[int],
        date_from: datetime,
        date_to: datetime,
        fields: List[str] = None,
        group_by_date: bool = False,
        include_video_metrics: bool = False
    ) -> Optional[Dict]:
        """
        Get statistics for specified campaigns and period

        Args:
            campaign_ids: List of campaign IDs
            date_from: Start date
            date_to: End date
            fields: List of fields to retrieve (default: shows, clicks, ctr)
            group_by_date: If True, group results by date (dateView)
            include_video_metrics: If True, include video completion metrics

        Returns:
            dict: Statistics data with total and per-campaign metrics
        """
        if not self.access_token:
            if not self.authenticate():
                return None

        # SAPE API supports 'fields' parameter to request specific metrics
        # For video campaigns, we need to request 'vastComplete' field explicitly

        try:
            request_body = {
                "dateViewFrom": date_from.strftime('%Y-%m-%d 00:00:00'),
                "dateViewTo": date_to.strftime('%Y-%m-%d 23:59:59'),
                "filters": [
                    {
                        "field": "campaignId",
                        "action": "in",
                        "values": campaign_ids
                    }
                ]
            }

            # Add fields parameter for video campaigns to get all completion metrics
            # SAPE API supports VAST quartiles: vastFirstQuartile, vastMidpoint, vastThirdQuartile, vastComplete
            if include_video_metrics:
                request_body["fields"] = [
                    "shows",
                    "clicks",
                    "vastStart",
                    "vastFirstQuartile",  # 25%
                    "vastMidpoint",        # 50%
                    "vastThirdQuartile",   # 75%
                    "vastComplete",        # 100%
                    "amount"
                ]
            else:
                request_body["fields"] = ["shows", "clicks", "amount"]

            print(f"📤 SAPE API Request:")
            print(f"   Campaign IDs: {campaign_ids}")
            print(f"   Date: {date_from.strftime('%Y-%m-%d')} to {date_to.strftime('%Y-%m-%d')}")
            print(f"   Fields: {request_body.get('fields')}")

            response = requests.post(
                f"{self.api_url}/statistics/extended",
                headers=self._get_headers(),
                json=request_body,
                timeout=30  # Increased from 10 to 30 seconds
            )

            if response.status_code == 200:
                data = response.json()
                rows_count = len(data.get('rows', []))
                stats_count = len(data.get('statistics', []))
                print(f"✅ SAPE API Response: rows={rows_count}, statistics={stats_count}")
                if stats_count == 0 and rows_count == 0:
                    print(f"   Response keys: {list(data.keys())}")
                    if 'statistics' in data:
                        print(f"   Statistics value: {data['statistics']}")
                return data
            else:
                print(f"❌ Error getting stats: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            print(f"❌ Error getting stats: {e}")
            import traceback
            traceback.print_exc()
            return None

    def get_stats_last_week(self, campaign_ids: List[int] = None) -> Optional[Dict]:
        """
        Get statistics for the last 7 days

        Args:
            campaign_ids: List of campaign IDs

        Returns:
            dict: Weekly statistics
        """
        date_to = datetime.now()
        date_from = date_to - timedelta(days=7)

        return self.get_stats(
            campaign_ids=campaign_ids,
            date_from=date_from,
            date_to=date_to
        )

    def calculate_metrics(self, stats_response: Dict) -> Dict:
        """
        Calculate aggregated metrics from stats response

        Args:
            stats_response: Response from get_stats()

        Returns:
            dict: Aggregated metrics (impressions, clicks, CTR)
        """
        if not stats_response:
            return {
                'impressions': 0,
                'clicks': 0,
                'ctr': 0.0
            }

        # Получаем totals из ответа
        total = stats_response.get('total', {})

        # SAPE использует 'shows' вместо 'impressions'
        impressions = total.get('shows', 0)
        clicks = total.get('clicks', 0)
        ctr = total.get('ctr', 0.0)

        return {
            'impressions': impressions,
            'clicks': clicks,
            'ctr': round(ctr, 2)
        }

    def get_daily_stats(
        self,
        campaign_ids: List[int],
        date_from: datetime,
        date_to: datetime,
        include_video_metrics: bool = False
    ) -> List[Dict]:
        """
        Get statistics grouped by date

        Args:
            campaign_ids: List of campaign IDs
            date_from: Start date
            date_to: End date
            include_video_metrics: If True, include video completion metrics

        Returns:
            list: List of daily statistics
                [
                    {
                        'date': '2026-04-15',
                        'impressions': 217116,
                        'clicks': 476,
                        'ctr': 0.22,
                        'completes': 15000  # Only if include_video_metrics=True
                    },
                    ...
                ]
        """
        stats = self.get_stats(
            campaign_ids=campaign_ids,
            date_from=date_from,
            date_to=date_to,
            group_by_date=True,
            include_video_metrics=include_video_metrics
        )

        if not stats:
            return []

        daily_data = []

        # SAPE API returns 'statistics' array, not 'rows'
        statistics = stats.get('statistics', [])

        if len(statistics) > 0:
            print(f"   First stat record: {statistics[0]}")

        for stat in statistics:
            # Извлекаем дату из строки
            date_str = stat.get('eventDate', '')
            if date_str:
                # Преобразуем формат даты из "2026-04-15" или "2026-04-15 00:00:00"
                if ' ' in date_str:
                    date_obj = datetime.strptime(date_str.split()[0], '%Y-%m-%d')
                else:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')

                impressions = stat.get('shows', 0)
                clicks = stat.get('clicks', 0)

                # Calculate CTR if not provided
                ctr = 0.0
                if impressions > 0:
                    ctr = round((clicks / impressions) * 100, 2)

                data_point = {
                    'date': date_obj.strftime('%d.%m.%Y'),  # Формат как в таблице
                    'date_iso': date_obj.strftime('%Y-%m-%d'),
                    'impressions': impressions,
                    'clicks': clicks,
                    'ctr': ctr
                }

                # Add video metrics if available
                # SAPE API returns VAST quartiles and completion metrics
                if include_video_metrics:
                    data_point['vastStart'] = stat.get('vastStart', 0)
                    data_point['vastFirstQuartile'] = stat.get('vastFirstQuartile', 0)  # 25%
                    data_point['vastMidpoint'] = stat.get('vastMidpoint', 0)            # 50%
                    data_point['vastThirdQuartile'] = stat.get('vastThirdQuartile', 0)  # 75%
                    data_point['vastComplete'] = stat.get('vastComplete', 0)            # 100%

                    # Aliases for compatibility with different naming conventions
                    data_point['vast25'] = data_point['vastFirstQuartile']
                    data_point['vast50'] = data_point['vastMidpoint']
                    data_point['vast75'] = data_point['vastThirdQuartile']
                    data_point['completes'] = data_point['vastComplete']

                    # Calculate VTR (Video Through Rate) - 100% completions / impressions
                    if impressions > 0 and data_point['vastComplete'] > 0:
                        data_point['vtr'] = round((data_point['vastComplete'] / impressions) * 100, 2)
                    else:
                        data_point['vtr'] = 0.0

                # Also include spent amount
                data_point['spent'] = stat.get('amount', 0)

                daily_data.append(data_point)

        return daily_data
