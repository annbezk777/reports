import gspread
from google.oauth2.service_account import Credentials
from typing import Dict, Optional, List
import random
import re
from datetime import datetime


class GoogleSheetsClient:
    """Client for Google Sheets API"""

    def __init__(self, credentials_file: str, scopes: list):
        """
        Initialize Google Sheets client

        Args:
            credentials_file: Path to service account JSON file
            scopes: List of Google API scopes
        """
        self.credentials_file = credentials_file
        self.scopes = scopes
        self.client = None

    def authenticate(self) -> bool:
        """
        Authenticate with Google Sheets API

        Returns:
            bool: True if authentication successful
        """
        try:
            creds = Credentials.from_service_account_file(
                self.credentials_file,
                scopes=self.scopes
            )
            self.client = gspread.authorize(creds)
            return True
        except Exception as e:
            print(f"Google Sheets auth error: {e}")
            return False

    def extract_sheet_id(self, url: str) -> Optional[str]:
        """
        Extract spreadsheet ID from Google Sheets URL

        Args:
            url: Google Sheets URL

        Returns:
            str: Spreadsheet ID or None
        """
        pattern = r'/spreadsheets/d/([a-zA-Z0-9-_]+)'
        match = re.search(pattern, url)
        return match.group(1) if match else None

    @staticmethod
    def get_worksheet_names(sheet_url: str) -> Optional[List[str]]:
        """
        Get list of ACTIVE (non-archived) worksheet names from a Google Sheets document

        Filters out:
        - Hidden worksheets
        - Worksheets with "Архив" or "[Архив]" prefix in title
        - Worksheets with "Archive" prefix

        Args:
            sheet_url: Google Sheets URL

        Returns:
            List of active worksheet names or None if error
        """
        try:
            # Create a temporary client instance
            client = GoogleSheetsClient('google_credentials.json', [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ])

            if not client.authenticate():
                return None

            # Extract sheet ID
            sheet_id = client.extract_sheet_id(sheet_url)
            if not sheet_id:
                return None

            # Open spreadsheet
            spreadsheet = client.client.open_by_key(sheet_id)

            # Get all worksheets (exclude hidden ones)
            all_worksheets = spreadsheet.worksheets(exclude_hidden=True)

            # Filter active (non-archived) worksheets
            active_worksheet_names = []

            for ws in all_worksheets:
                title = ws.title

                # Skip if title starts with archive markers
                if (title.startswith('Архив') or
                    title.startswith('[Архив]') or
                    title.startswith('Archive') or
                    title.startswith('[Archive]') or
                    title.lower().startswith('архив') or
                    title.lower().startswith('archive')):
                    print(f"📦 Skipping archived worksheet: {title}")
                    continue

                active_worksheet_names.append(title)

            print(f"✅ Found {len(active_worksheet_names)} active worksheets (filtered {len(all_worksheets) - len(active_worksheet_names)} archived)")

            return active_worksheet_names

        except Exception as e:
            print(f"Error getting worksheet names: {e}")
            import traceback
            traceback.print_exc()
            return None

    def update_cells(
        self,
        sheet_url: str,
        sheet_name: Optional[str],
        cell_values: Dict[str, any]
    ) -> bool:
        """
        Update specific cells in Google Sheet

        Args:
            sheet_url: Google Sheets URL
            sheet_name: Worksheet name (None = first sheet)
            cell_values: Dict of {cell_address: value}, e.g., {'B5': 1000, 'C5': 500}

        Returns:
            bool: True if update successful
        """
        if not self.client:
            if not self.authenticate():
                return False

        try:
            # Use cached worksheet if provided to avoid API quota
            if cached_worksheet is not None:
                worksheet = cached_worksheet
                print(f"✅ Using cached worksheet (saves API quota)")
            else:
                # Extract spreadsheet ID
                sheet_id = self.extract_sheet_id(sheet_url)
                if not sheet_id:
                    print("Invalid Google Sheets URL")
                    return False

                # Open spreadsheet
                spreadsheet = self.client.open_by_key(sheet_id)

                # Select worksheet
                if sheet_name:
                    worksheet = spreadsheet.worksheet(sheet_name)
                else:
                    worksheet = spreadsheet.get_worksheet(0)  # First sheet

            # Update cells
            for cell_address, value in cell_values.items():
                worksheet.update(cell_address, value)

            return True

        except Exception as e:
            print(f"Error updating cells: {e}")
            return False

    def write_metrics(
        self,
        sheet_url: str,
        sheet_name: Optional[str],
        metrics: Dict,
        cell_mapping: Dict[str, str]
    ) -> bool:
        """
        Write metrics to Google Sheet based on cell mapping

        Args:
            sheet_url: Google Sheets URL
            sheet_name: Worksheet name
            metrics: Dict with metrics {'impressions': 1000, 'clicks': 50, 'ctr': 5.0}
            cell_mapping: Dict mapping metric names to cells
                {'impressions_cell': 'B5', 'clicks_cell': 'C5', 'ctr_cell': 'D5'}

        Returns:
            bool: True if write successful
        """
        cell_values = {}

        # Map metrics to cells
        if 'impressions_cell' in cell_mapping and 'impressions' in metrics:
            cell_values[cell_mapping['impressions_cell']] = metrics['impressions']

        if 'clicks_cell' in cell_mapping and 'clicks' in metrics:
            cell_values[cell_mapping['clicks_cell']] = metrics['clicks']

        if 'ctr_cell' in cell_mapping and 'ctr' in metrics:
            cell_values[cell_mapping['ctr_cell']] = f"{metrics['ctr']}%"

        # Add date if specified
        if 'date_cell' in cell_mapping:
            from datetime import datetime
            cell_values[cell_mapping['date_cell']] = datetime.now().strftime('%d.%m.%Y %H:%M')

        return self.update_cells(sheet_url, sheet_name, cell_values)

    def get_worksheet_object(
        self,
        sheet_url: str,
        sheet_name: Optional[str]
    ):
        """
        Get worksheet object for reuse (to avoid API quota)

        Returns:
            worksheet object or None
        """
        if not self.client:
            if not self.authenticate():
                return None

        try:
            sheet_id = self.extract_sheet_id(sheet_url)
            if not sheet_id:
                return None

            spreadsheet = self.client.open_by_key(sheet_id)

            if sheet_name:
                worksheet = spreadsheet.worksheet(sheet_name)
            else:
                worksheet = spreadsheet.get_worksheet(0)

            return worksheet

        except Exception as e:
            print(f"❌ Error getting worksheet: {e}")
            return None

    def extract_brand_from_sheet(
        self,
        sheet_url: str,
        sheet_name: Optional[str],
        cached_worksheet=None
    ) -> Optional[str]:
        """
        Extract brand name from Google Sheets by searching for 'Бренд:' label in first 10 rows

        Args:
            sheet_url: Google Sheets URL
            sheet_name: Worksheet name
            cached_worksheet: Optional cached worksheet object to avoid API calls

        Returns:
            Brand name or None if not found
        """
        try:
            # Use cached worksheet if provided
            if cached_worksheet is not None:
                worksheet = cached_worksheet
                print(f"✅ Using cached worksheet for brand extraction")
            else:
                # Get worksheet object
                worksheet = self.get_worksheet_object(sheet_url, sheet_name)
                if not worksheet:
                    print(f"❌ Could not get worksheet for brand extraction")
                    return None

            # Read first 10 rows, all columns A-Z
            print(f"🔍 Searching for 'Бренд' in first 10 rows...")
            data = worksheet.get('A1:Z10')

            if not data:
                print(f"⚠️ No data found in first 10 rows")
                return None

            # Search for "Бренд:" or "Бренд" in each row
            for row_idx, row in enumerate(data, start=1):
                for col_idx, cell_value in enumerate(row):
                    if cell_value and isinstance(cell_value, str):
                        # Check if cell contains "Бренд" (case-insensitive)
                        if 'бренд' in cell_value.lower():
                            print(f"✅ Found 'Бренд' label at row {row_idx}, col {col_idx + 1}: '{cell_value}'")

                            # Try to get value from next cell (to the right)
                            if col_idx + 1 < len(row):
                                brand_value = row[col_idx + 1]
                                if brand_value and str(brand_value).strip():
                                    print(f"✅ Extracted brand: '{brand_value}'")
                                    return str(brand_value).strip()

                            # If no value to the right, check next row same column
                            if row_idx < len(data):
                                next_row = data[row_idx]
                                if col_idx < len(next_row):
                                    brand_value = next_row[col_idx]
                                    if brand_value and str(brand_value).strip():
                                        print(f"✅ Extracted brand from row below: '{brand_value}'")
                                        return str(brand_value).strip()

            print(f"⚠️ 'Бренд' label not found in first 10 rows")
            return None

        except Exception as e:
            print(f"❌ Error extracting brand: {e}")
            import traceback
            traceback.print_exc()
            return None

    def read_worksheet_once(
        self,
        sheet_url: str,
        sheet_name: Optional[str]
    ) -> Optional[List[List]]:
        """
        Read worksheet data once and return it for caching
        This reduces API calls when searching for multiple campaigns

        Returns:
            list: All data from worksheet (up to DZ150)
        """
        if not self.client:
            if not self.authenticate():
                return None

        try:
            sheet_id = self.extract_sheet_id(sheet_url)
            if not sheet_id:
                return None

            spreadsheet = self.client.open_by_key(sheet_id)

            if sheet_name:
                worksheet = spreadsheet.worksheet(sheet_name)
            else:
                worksheet = spreadsheet.get_worksheet(0)

            # Read all data once
            all_data = worksheet.get('A1:DZ300')
            return all_data

        except Exception as e:
            print(f"❌ Error reading worksheet: {e}")
            return None


    def find_all_sections_for_campaign(
        self,
        sheet_url: str,
        sheet_name: Optional[str],
        campaign_id: str,
        cached_data: Optional[List[List]] = None
    ) -> List[Dict]:
        """
        Find ALL table sections that contain this campaign ID

        Args:
            sheet_url: Google Sheets URL
            sheet_name: Worksheet name
            campaign_id: Campaign ID to search for
            cached_data: Optional cached worksheet data

        Returns:
            List of structure dicts (one for each section found)
        """
        all_sections = []

        # First detect all sections using the standard method, but collect ALL matches
        structures = self.auto_detect_all_structures(sheet_url, sheet_name, campaign_id, cached_data)

        return structures

    def auto_detect_all_structures(
        self,
        sheet_url: str,
        sheet_name: Optional[str],
        campaign_id: str,
        cached_data: Optional[List[List]] = None
    ) -> List[Dict]:
        """
        Find ALL structures (sections) containing this campaign ID

        Returns:
            List of structure dicts
        """
        if not self.client:
            if not self.authenticate():
                return []

        try:
            # Extract spreadsheet ID
            sheet_id = self.extract_sheet_id(sheet_url)
            if not sheet_id:
                print("Invalid Google Sheets URL")
                return []

            # Open spreadsheet
            spreadsheet = self.client.open_by_key(sheet_id)

            # Select worksheet
            if sheet_name:
                worksheet = spreadsheet.worksheet(sheet_name)
            else:
                worksheet = spreadsheet.get_worksheet(0)

            # Read data
            if cached_data is not None:
                all_data = cached_data
            else:
                all_data = worksheet.get('A1:DZ300')

            # Find ALL headers containing this campaign ID
            found_sections = []

            # DEBUG: Log what we're searching for
            print(f"\n🔍 DEBUG auto_detect_all_structures:")
            print(f"   Searching for campaign_id: '{campaign_id}' (type: {type(campaign_id).__name__})")
            print(f"   Worksheet has {len(all_data)} rows")

            # DEBUG: Track all headers found
            all_headers_found = []

            for row_idx, row in enumerate(all_data):
                if not row:
                    continue
                for col_idx, cell in enumerate(row):
                    if not cell:
                        continue

                    cell_str = str(cell)

                    # Check if cell contains campaign IDs (6-digit numbers)
                    found_ids = re.findall(r'(?:ID\s*)?(\d{6})\b', cell_str)

                    # Skip if no IDs found
                    if not found_ids:
                        continue

                    # This is a potential header with campaign IDs
                    # Accept if: contains "Показатели кампании" OR contains multiple 6-digit IDs
                    is_campaign_header = (
                        'Показатели кампании' in cell_str or  # Old format
                        len(found_ids) >= 1  # New format: just IDs (accept even single ID)
                    )

                    if is_campaign_header:
                        # DEBUG: Log every header found
                        all_headers_found.append({
                            'row': row_idx + 1,
                            'col': col_idx + 1,
                            'text': cell_str,
                            'ids': found_ids
                        })

                        print(f"   📋 Found header at row {row_idx + 1}, col {col_idx + 1}:")
                        print(f"      Text: '{cell_str}'")
                        print(f"      Extracted IDs: {found_ids}")
                        print(f"      Match with '{campaign_id}'? {campaign_id in found_ids}")

                        if campaign_id in found_ids:
                            print(f"      ✅ MATCH! Processing section...")
                            # Found a section! Parse it
                            section_structure = self._parse_section_structure(
                                all_data=all_data,
                                header_row_idx=row_idx,
                                header_col_idx=col_idx,
                                header_cell_content=cell_str,
                                found_ids=found_ids
                            )

                            if section_structure:
                                found_sections.append(section_structure)
                                print(f"      ✅ Section parsed successfully")
                            else:
                                print(f"      ⚠️ Section parsing failed")
                        else:
                            print(f"      ❌ No match ('{campaign_id}' not in {found_ids})")

            # DEBUG: Summary
            print(f"\n📊 Summary:")
            print(f"   Total headers with campaign IDs: {len(all_headers_found)}")
            print(f"   Sections matched for campaign {campaign_id}: {len(found_sections)}")

            if len(all_headers_found) > 0 and len(found_sections) == 0:
                print(f"\n⚠️ WARNING: Found headers but no matches!")
                print(f"   All IDs found in headers: {[h['ids'] for h in all_headers_found]}")
                print(f"   Looking for: '{campaign_id}' (type: {type(campaign_id).__name__})")

            return found_sections

        except Exception as e:
            print(f"❌ Error in auto_detect_all_structures: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _parse_section_structure(
        self,
        all_data: List[List],
        header_row_idx: int,
        header_col_idx: int,
        header_cell_content: str,
        found_ids: List[str]
    ) -> Optional[Dict]:
        """
        Parse structure for a single section

        Returns:
            Structure dict or None if parsing failed
        """
        try:
            header_row = header_row_idx + 1

            # Helper: convert column index to letter
            def col_idx_to_letter(idx):
                result = ''
                while idx >= 0:
                    result = chr(65 + (idx % 26)) + result
                    idx = idx // 26 - 1
                return result

            # Find column headers row (contains "Дата")
            column_headers_row = None

            for offset in range(1, 6):
                test_row = header_row + offset
                if test_row - 1 < len(all_data):
                    row_data = all_data[test_row - 1]
                    # Check if this row has "Дата" in the same column area
                    if row_data and len(row_data) > header_col_idx:
                        # Look for "Дата" within ±2 columns
                        for check_col in range(max(0, header_col_idx - 2), min(len(row_data), header_col_idx + 3)):
                            if row_data[check_col] and 'дата' in str(row_data[check_col]).lower():
                                column_headers_row = test_row
                                break
                if column_headers_row:
                    break

            if not column_headers_row:
                return None

            # Get headers
            if column_headers_row - 1 < len(all_data):
                headers = all_data[column_headers_row - 1]
            else:
                return None

            # Map columns - search near the header column
            structure = {
                'data_start_row': column_headers_row + 1,
                'date_column': None,
                'impressions_column': None,
                'reach_column': None,
                'clicks_column': None,
                'ctr_column': None,
                'spent_column': None,
                'completes_column': None,  # Video completion column
                'vast25_column': None,
                'vast50_column': None,
                'vast75_column': None,
                'campaign_ids': found_ids,
                'header_row': header_row,
                'header_col': col_idx_to_letter(header_col_idx)
            }

            # Search for columns within reasonable range of the header
            # Include columns to the LEFT of header (for tables where Дата is before campaign name)
            search_start = max(0, header_col_idx - 3)  # Look 3 columns left
            search_end = min(len(headers), header_col_idx + 10)  # Look 10 columns right

            for i in range(search_start, search_end):
                if i >= len(headers):
                    break

                header = str(headers[i]).lower() if headers[i] else ''

                if 'дата' in header and not structure['date_column']:
                    structure['date_column'] = col_idx_to_letter(i)
                elif 'показ' in header and not structure['impressions_column']:
                    structure['impressions_column'] = col_idx_to_letter(i)
                elif 'охват' in header and not structure['reach_column']:
                    structure['reach_column'] = col_idx_to_letter(i)
                elif 'клик' in header and not structure['clicks_column']:
                    structure['clicks_column'] = col_idx_to_letter(i)
                elif 'ctr' in header and not structure['ctr_column']:
                    structure['ctr_column'] = col_idx_to_letter(i)
                elif ('потрачено' in header or 'spent' in header) and not structure['spent_column']:
                    structure['spent_column'] = col_idx_to_letter(i)
                # ВАЖНО: Проверяем специфичные проценты РАНЬШЕ общего "досмотр"
                elif '25%' in header and not structure['vast25_column']:
                    structure['vast25_column'] = col_idx_to_letter(i)
                elif '50%' in header and not structure['vast50_column']:
                    structure['vast50_column'] = col_idx_to_letter(i)
                elif '75%' in header and not structure['vast75_column']:
                    structure['vast75_column'] = col_idx_to_letter(i)
                elif '100%' in header and not structure['completes_column']:
                    # Column for video completions (100% views)
                    structure['completes_column'] = col_idx_to_letter(i)

            # Verify required columns found
            if not all([structure['date_column'], structure['impressions_column'], structure['reach_column']]):
                return None

            return structure

        except Exception as e:
            print(f"❌ Error parsing section structure: {e}")
            return None

    def auto_detect_structure(
        self,
        sheet_url: str,
        sheet_name: Optional[str],
        campaign_id: str,
        cached_data: Optional[List[List]] = None
    ) -> Optional[Dict]:
        """
        Auto-detect table structure by finding campaign ID in header (returns FIRST match only)

        Args:
            cached_data: Optional pre-read worksheet data to avoid multiple API calls

        Returns:
            dict: Structure with columns and ALL campaign IDs from header
        """
        if not self.client:
            if not self.authenticate():
                return None

        try:
            # Extract spreadsheet ID
            sheet_id = self.extract_sheet_id(sheet_url)
            if not sheet_id:
                print("Invalid Google Sheets URL")
                return None

            # Open spreadsheet
            spreadsheet = self.client.open_by_key(sheet_id)

            # Select worksheet
            if sheet_name:
                worksheet = spreadsheet.worksheet(sheet_name)
            else:
                worksheet = spreadsheet.get_worksheet(0)

            # Read data (use cache if available to save API calls)
            print(f"🔍 Searching for campaign ID: {campaign_id}...")
            if cached_data is not None:
                all_data = cached_data
                print(f"📊 Using cached data: {len(all_data)} rows")
                # DEBUG: Show if data is empty
                if len(all_data) == 0:
                    print(f"⚠️ WARNING: Cached data is EMPTY!")
                else:
                    # Show first few cells to verify data format
                    first_row_sample = []
                    if all_data and len(all_data) > 0 and all_data[0]:
                        first_row_sample = [str(cell)[:30] for cell in all_data[0][:5] if cell]
                    print(f"📋 First row sample: {first_row_sample[:3] if first_row_sample else 'EMPTY'}")
            else:
                all_data = worksheet.get('A1:DZ300')
                print(f"📊 Read from API: {len(all_data)} rows")

            # DEBUG: Find all 6-digit IDs in entire table to help troubleshoot
            # Supports both "282304" and "ID 282304" formats
            all_found_ids = set()
            for row_idx, row in enumerate(all_data):
                if not row:
                    continue
                for cell in row:
                    if cell:
                        found = re.findall(r'(?:ID\s*)?(\d{6})\b', str(cell))
                        all_found_ids.update(found)

            if all_found_ids:
                print(f"📋 All campaign IDs found in table: {sorted(all_found_ids)}")
            else:
                print(f"⚠️ WARNING: No 6-digit campaign IDs found in table!")

            # DEBUG: Show what's on row 45 specifically
            if len(all_data) >= 45:
                row_45 = all_data[44]  # 0-indexed, so row 45 is index 44
                row_45_text = [str(cell)[:50] for cell in row_45 if cell]
                print(f"🔍 DEBUG Row 45 content: {row_45_text[:5] if row_45_text else 'EMPTY'}")

            # Find campaign ID in headers - FLEXIBLE SEARCH (accepts any format)
            header_row = None
            header_col_idx = None
            header_cell_content = None

            # Search for ANY cell containing this campaign ID (flexible, no restrictions)
            for row_idx, row in enumerate(all_data):
                if not row:
                    continue
                for col_idx, cell in enumerate(row):
                    if not cell:
                        continue

                    cell_str = str(cell)
                    # Look for 6-digit campaign IDs
                    found_ids = re.findall(r'(?:ID\s*)?(\d{6})\b', cell_str)

                    # Skip if no IDs found
                    if not found_ids:
                        continue

                    # Check if our campaign ID is in this cell
                    if campaign_id in found_ids:
                        # Accept any cell with campaign IDs (no format restrictions)
                        header_row = row_idx + 1
                        header_col_idx = col_idx
                        header_cell_content = cell_str
                        print(f"✅ Found campaign {campaign_id} in row {header_row}")
                        print(f"   Cell content: '{cell_str}'")
                        print(f"   All IDs in header: {found_ids}")
                        break

                if header_row:
                    break

            # If still not found, show debug info
            if not header_row:
                print(f"🔍 Campaign ID {campaign_id} not found, trying alternative search...")

                for row_idx, row in enumerate(all_data):  # Search ALL rows
                    if not row:
                        continue
                    for col_idx, cell in enumerate(row):
                        if not cell:
                            continue

                        cell_str = str(cell)
                        # Look for 6-digit campaign IDs (supports "ID 282304" format)
                        found_ids = re.findall(r'(?:ID\s*)?(\d{6})\b', cell_str)

                        if campaign_id in found_ids:
                            # Found the ID! Now check if this looks like a header row
                            # (should have multiple columns with data nearby)
                            header_row = row_idx + 1
                            header_col_idx = col_idx
                            header_cell_content = cell_str
                            print(f"✅ Found campaign {campaign_id} in row {header_row} (method 2: flexible search)")
                            print(f"   Cell content: '{cell_str}'")
                            print(f"   All IDs found: {found_ids}")
                            break

                    if header_row:
                        break

            if not header_row:
                print(f"❌ Campaign ID {campaign_id} not found in table")
                print(f"   Worksheet: '{sheet_name if sheet_name else 'Default'}'")
                print(f"   Searched entire table ({len(all_data)} rows) for pattern: 6-digit number matching '{campaign_id}'")
                print(f"   All IDs found in table: {sorted(all_found_ids) if all_found_ids else 'NONE'}")
                if all_found_ids:
                    # Show which IDs are close (helpful for typos)
                    similar_ids = [id for id in all_found_ids if id.startswith(campaign_id[:3])]
                    if similar_ids:
                        print(f"   ⚠️ Similar IDs found (check for typos): {sorted(similar_ids)}")
                print(f"   Please check that campaign ID is present in sheet headers")
                return None

            # Extract all campaign IDs from header (supports "ID 282304" format)
            campaign_ids = re.findall(r'(?:ID\s*)?(\d{6})\b', header_cell_content) if header_cell_content else []

            # Helper: convert column index to letter
            def col_idx_to_letter(idx):
                result = ''
                while idx >= 0:
                    result = chr(65 + (idx % 26)) + result
                    idx = idx // 26 - 1
                return result

            # Find column headers row (contains "Дата")
            column_headers_row = None
            start_col = col_idx_to_letter(header_col_idx)
            end_col_idx = header_col_idx + 7
            end_col = col_idx_to_letter(end_col_idx)

            for offset in range(1, 6):
                test_row = header_row + offset
                if test_row - 1 < len(all_data):
                    row_data = all_data[test_row - 1]
                    if row_data and any(cell and 'дата' in str(cell).lower() for cell in row_data):
                        column_headers_row = test_row
                        print(f"✅ Found headers in row {column_headers_row}")
                        break

            if not column_headers_row:
                print(f"❌ Could not find headers row")
                return None

            # Get headers
            if column_headers_row - 1 < len(all_data):
                headers = all_data[column_headers_row - 1]
            else:
                return None

            # Map columns
            structure = {
                'data_start_row': column_headers_row + 1,
                'date_column': None,
                'impressions_column': None,
                'reach_column': None,
                'clicks_column': None,
                'ctr_column': None,
                'vast25_column': None,      # Досмотры 25%
                'vast50_column': None,      # Досмотры 50%
                'vast75_column': None,      # Досмотры 75%
                'completes_column': None,   # Досмотры 100%
                'spent_column': None,
                'campaign_ids': campaign_ids
            }

            column_mapping = {
                'дата': 'date_column',
                'показы': 'impressions_column',
                'shows': 'impressions_column',
                'охват': 'reach_column',
                'reach': 'reach_column',
                'клики': 'clicks_column',
                'clicks': 'clicks_column',
                'ctr': 'ctr_column',
                'досмотры 25%': 'vast25_column',
                'досмотры 25': 'vast25_column',
                '25%': 'vast25_column',
                'досмотры 50%': 'vast50_column',
                'досмотры 50': 'vast50_column',
                '50%': 'vast50_column',
                'досмотры 75%': 'vast75_column',
                'досмотры 75': 'vast75_column',
                '75%': 'vast75_column',
                'досмотры 100%': 'completes_column',
                'досмотры 100': 'completes_column',
                'досмотры': 'completes_column',
                'completes': 'completes_column',
                'complete': 'completes_column',
                '100%': 'completes_column',
                'потрачено': 'spent_column',
                'spent': 'spent_column'
            }

            print(f"🔍 DEBUG: Searching headers in row {column_headers_row}")
            print(f"   Total headers count: {len(headers)}")

            # Only search in the range of this campaign section
            # Start from header_col_idx and search up to 10 columns
            search_start = header_col_idx
            search_end = min(header_col_idx + 10, len(headers))

            print(f"   Searching columns {search_start} to {search_end}")
            for i in range(search_start, search_end):
                if i < len(headers) and headers[i]:
                    print(f"   Col {i} ({col_idx_to_letter(i)}): '{headers[i]}'")

            for col_idx, header in enumerate(headers):
                if not header:
                    continue  # Changed from break to continue

                # Only process columns in this campaign's section
                if col_idx < header_col_idx or col_idx >= header_col_idx + 10:
                    continue

                header_lower = str(header).lower().strip()
                for key, field in column_mapping.items():
                    if key in header_lower:
                        # Only set if not already set (don't overwrite with duplicate headers)
                        if not structure[field]:
                            actual_col_idx = col_idx
                            col_letter = col_idx_to_letter(actual_col_idx)
                            structure[field] = col_letter
                            print(f"   ✅ Mapped '{header}' → {field} = {col_letter}")
                        break

            print(f"Auto-detected structure: {structure}")
            return structure

        except Exception as e:
            print(f"Error auto-detecting structure: {e}")
            import traceback
            traceback.print_exc()
            return None

    def check_section_has_fresh_data(
        self,
        sheet_url: str,
        sheet_name: Optional[str],
        column_mapping: Dict[str, str],
        data_start_row: int,
        expected_dates: List[str],
        cached_worksheet=None
    ) -> bool:
        """
        Check if section already has fresh data for the requested period

        Args:
            sheet_url: Google Sheets URL
            sheet_name: Worksheet name
            column_mapping: Column mapping with impressions_column
            data_start_row: Starting row of data
            expected_dates: List of dates we expect to write (e.g., ['01.04.2026', '02.04.2026'])
            cached_worksheet: Optional pre-opened worksheet to avoid API quota

        Returns:
            bool: True if section has data for at least 80% of expected dates
        """
        if not self.client:
            if not self.authenticate():
                return False

        try:
            # Use cached worksheet if provided
            if cached_worksheet is not None:
                worksheet = cached_worksheet
            else:
                sheet_id = self.extract_sheet_id(sheet_url)
                if not sheet_id:
                    return False

                spreadsheet = self.client.open_by_key(sheet_id)
                if sheet_name:
                    worksheet = spreadsheet.worksheet(sheet_name)
                else:
                    worksheet = spreadsheet.get_worksheet(0)

            # Check if impressions column has data
            impressions_col = column_mapping.get('impressions_column')
            if not impressions_col:
                return False

            # Read first 35 rows of data (typical month)
            check_range = f"{impressions_col}{data_start_row}:{impressions_col}{data_start_row + 34}"
            impressions_data = worksheet.get(check_range)

            # Count non-empty cells
            non_empty_count = 0
            for row in impressions_data:
                if row and row[0] and str(row[0]).strip() and str(row[0]).strip() != '0':
                    non_empty_count += 1

            # If we have data for at least 80% of expected dates, consider it fresh
            expected_count = len(expected_dates)
            has_enough_data = non_empty_count >= (expected_count * 0.8)

            print(f"   📊 Fresh data check: {non_empty_count}/{expected_count} days have data ({int(non_empty_count/expected_count*100) if expected_count > 0 else 0}%)")

            return has_enough_data

        except Exception as e:
            print(f"   ⚠️ Could not check for fresh data: {e}")
            return False  # If check fails, assume no data and process anyway

    def write_daily_data(
        self,
        sheet_url: str,
        sheet_name: Optional[str],
        daily_data: List[Dict],
        column_mapping: Dict[str, str],
        data_start_row: int,
        daily_frequency: float = 3.0,
        daily_variance: float = 0.1,
        total_frequency: float = 3.0,
        total_variance: float = 0.1,
        # OLD PARAMETERS (kept for backward compatibility, not used in new logic):
        frequency: float = 4.0,
        frequency_variance: float = 0.5,
        total_reach_coefficient: float = 0.96,
        cached_worksheet=None
    ) -> bool:
        """
        Write daily statistics to Google Sheet

        Args:
            sheet_url: Google Sheets URL
            sheet_name: Worksheet name (None = first sheet)
            daily_data: List of daily statistics from SAPE API
                [{'date': '15.04.2026', 'impressions': 217116, 'clicks': 476, 'ctr': 0.22}, ...]
            column_mapping: Dict mapping metric names to columns
                {'date_column': 'A', 'impressions_column': 'B', 'reach_column': 'C', 'clicks_column': 'D', 'ctr_column': 'E'}
            data_start_row: Row number where data starts (e.g., 2)
            daily_frequency: Maximum daily frequency for daily reach calculation (default: 3.0)
            daily_variance: Variance for daily frequency (default: 0.1)
                Example: daily_freq=3.0, variance=0.1 -> range 2.9-3.0 (NEVER exceeds max!)
            total_frequency: Maximum total frequency for total reach calculation (default: 3.0)
            total_variance: Variance for total frequency (default: 0.1)
                Example: total_freq=3.0, variance=0.1 -> range 2.9-3.0 (NEVER exceeds max!)
            cached_worksheet: Optional pre-opened worksheet to avoid API quota
            frequency, frequency_variance, total_reach_coefficient: DEPRECATED (kept for compatibility)

        Returns:
            bool: True if write successful
        """
        if not self.client:
            if not self.authenticate():
                return False

        try:
            # Use cached worksheet if provided (saves API quota!)
            if cached_worksheet is not None:
                worksheet = cached_worksheet
                print(f"✅ Using cached worksheet (saves API quota)")
            else:
                # Extract spreadsheet ID
                sheet_id = self.extract_sheet_id(sheet_url)
                if not sheet_id:
                    print("Invalid Google Sheets URL")
                    return False

                # Open spreadsheet (only if no cached worksheet)
                spreadsheet = self.client.open_by_key(sheet_id)

                # Select worksheet
                if sheet_name:
                    worksheet = spreadsheet.worksheet(sheet_name)
                else:
                    worksheet = spreadsheet.get_worksheet(0)

            # Get date column to find matching rows
            date_col = column_mapping.get('date_column', 'A')

            # First, find the "Всего" row to determine section boundary
            # Read up to 50 rows to find section end
            search_range = f"{date_col}{data_start_row}:{date_col}{data_start_row + 50}"

            # Retry logic for 429 errors
            try:
                search_dates = worksheet.get(search_range)
            except Exception as e:
                if '429' in str(e) or 'Quota exceeded' in str(e) or 'RATE_LIMIT_EXCEEDED' in str(e):
                    print(f"⚠️ Google Sheets API quota exceeded (429) while searching for 'Всего'. Waiting 65 seconds...")
                    import time
                    time.sleep(65)
                    print(f"🔄 Retrying search after quota cooldown...")
                    try:
                        search_dates = worksheet.get(search_range)
                        print(f"✅ Retry successful!")
                    except Exception as retry_error:
                        print(f"❌ Retry also failed: {retry_error}")
                        return False
                else:
                    print(f"❌ Error reading search range: {e}")
                    return False

            # Find where "Всего" appears (marks end of section)
            section_end_offset = 35  # Default: 35 rows (enough for monthly data)
            total_row = None  # Cache for later use (avoid duplicate search)
            for i, row in enumerate(search_dates):
                if row and row[0] and 'всего' in str(row[0]).lower():
                    section_end_offset = i
                    total_row = data_start_row + i  # CACHE: Save row number for later
                    print(f"📍 Found section boundary 'Всего' at row {total_row} (offset {i} from data start)")
                    break

            # Read dates only within this section boundary
            date_range = f"{date_col}{data_start_row}:{date_col}{data_start_row + section_end_offset - 1}"

            # Retry logic for 429 errors
            try:
                existing_dates = worksheet.get(date_range)
            except Exception as e:
                if '429' in str(e) or 'Quota exceeded' in str(e) or 'RATE_LIMIT_EXCEEDED' in str(e):
                    print(f"⚠️ Google Sheets API quota exceeded (429) while reading dates. Waiting 65 seconds...")
                    import time
                    time.sleep(65)
                    print(f"🔄 Retrying date read after quota cooldown...")
                    try:
                        existing_dates = worksheet.get(date_range)
                        print(f"✅ Retry successful!")
                    except Exception as retry_error:
                        print(f"❌ Retry also failed: {retry_error}")
                        return False
                else:
                    print(f"❌ Error reading dates: {e}")
                    return False

            # Create a mapping of date -> row number
            date_to_row = {}
            for i, row in enumerate(existing_dates):
                if row and row[0]:  # If cell is not empty
                    # Skip "Всего" row itself
                    if 'всего' not in str(row[0]).lower():
                        date_to_row[row[0]] = data_start_row + i

            print(f"📅 DEBUG: Found {len(date_to_row)} dates in sheet")
            if len(date_to_row) > 0:
                first_few = list(date_to_row.keys())[:5]
                print(f"   First dates in sheet: {first_few}")

            # Prepare batch update
            updates = []

            print(f"📅 DEBUG: Processing {len(daily_data)} days from SAPE API")
            for idx, day_data in enumerate(daily_data):
                date_str = day_data['date']
                if idx == 0:
                    print(f"   First date from SAPE: '{date_str}'")

                # Find the row for this date
                if date_str not in date_to_row:
                    print(f"⚠️ Date '{date_str}' not found in sheet, skipping")
                    print(f"   Available dates sample: {list(date_to_row.keys())[:10]}")
                    continue
                else:
                    print(f"✅ Found date '{date_str}' at row {date_to_row[date_str]}")

                row_num = date_to_row[date_str]

                # Calculate reach using daily frequency settings
                # NEW LOGIC: Daily frequency = random(freq - variance, freq)
                # CRITICAL: Frequency NEVER exceeds daily_frequency!
                impressions = day_data.get('impressions', 0)
                if impressions > 0:
                    # Calculate MIN and MAX for daily frequency
                    # daily_frequency = maximum value
                    # daily_variance = how much DOWN we can go
                    min_freq = max(1.0, daily_frequency - daily_variance)  # Don't go below 1.0
                    max_freq = daily_frequency  # CRITICAL: Max is the frequency itself!

                    # Random daily frequency within range (always ≤ daily_frequency)
                    actual_frequency = random.uniform(min_freq, max_freq)
                    reach = int(impressions / actual_frequency)

                    if idx == 0:
                        print(f"   📊 Daily frequency (max): {max_freq:.2f}, variance: {daily_variance:.2f}")
                        print(f"   📊 Daily range: {min_freq:.2f} - {max_freq:.2f}")
                        print(f"   📊 Today's random frequency: {actual_frequency:.5f}")
                else:
                    reach = 0

                # Prepare cell updates for this row
                cells_added_for_row = []

                if 'impressions_column' in column_mapping and column_mapping['impressions_column']:
                    cell = f"{column_mapping['impressions_column']}{row_num}"
                    updates.append({'range': cell, 'values': [[impressions]]})
                    cells_added_for_row.append(f"impressions={impressions}")

                if 'reach_column' in column_mapping and column_mapping['reach_column']:
                    cell = f"{column_mapping['reach_column']}{row_num}"
                    updates.append({'range': cell, 'values': [[reach]]})
                    cells_added_for_row.append(f"reach={reach}")

                if 'clicks_column' in column_mapping and column_mapping['clicks_column']:
                    cell = f"{column_mapping['clicks_column']}{row_num}"
                    clicks = day_data.get('clicks', 0)
                    updates.append({'range': cell, 'values': [[clicks]]})
                    cells_added_for_row.append(f"clicks={clicks}")

                if idx == 0 and cells_added_for_row:
                    print(f"   First row updates: {', '.join(cells_added_for_row)}")

                # CTR не записываем - рассчитывается по формуле в таблице
                # if 'ctr_column' in column_mapping:
                #     cell = f"{column_mapping['ctr_column']}{row_num}"
                #     ctr = day_data.get('ctr', 0.0)
                #     ctr_formatted = f"{ctr}%"
                #     updates.append({'range': cell, 'values': [[ctr_formatted]]})

                # Add video completion metrics (quartiles) if available
                # Write vast25 (25% completion)
                if 'vast25_column' in column_mapping and column_mapping['vast25_column']:
                    vast25 = day_data.get('vast25', day_data.get('vastFirstQuartile', 0))
                    cell = f"{column_mapping['vast25_column']}{row_num}"
                    updates.append({'range': cell, 'values': [[vast25]]})

                # Write vast50 (50% completion)
                if 'vast50_column' in column_mapping and column_mapping['vast50_column']:
                    vast50 = day_data.get('vast50', day_data.get('vastMidpoint', 0))
                    cell = f"{column_mapping['vast50_column']}{row_num}"
                    updates.append({'range': cell, 'values': [[vast50]]})

                # Write vast75 (75% completion)
                if 'vast75_column' in column_mapping and column_mapping['vast75_column']:
                    vast75 = day_data.get('vast75', day_data.get('vastThirdQuartile', 0))
                    cell = f"{column_mapping['vast75_column']}{row_num}"
                    updates.append({'range': cell, 'values': [[vast75]]})

                # Write completes (100% completion)
                if 'completes_column' in column_mapping and column_mapping['completes_column']:
                    completes = day_data.get('completes', day_data.get('vastComplete', 0))
                    cell = f"{column_mapping['completes_column']}{row_num}"
                    updates.append({'range': cell, 'values': [[completes]]})

            # Batch update all cells
            if updates:
                print(f"📝 DEBUG: Preparing to batch_update {len(updates)} cells")
                print(f"   First 3 updates: {updates[:3] if len(updates) >= 3 else updates}")
                try:
                    print(f"🔧 DEBUG: About to call worksheet.batch_update() for worksheet: {sheet_name}")
                    worksheet.batch_update(updates)
                    print(f"✅ Updated {len(daily_data)} days in Google Sheets ({len(updates)} cells written)")
                except Exception as batch_error:
                    # Check if this is a quota exceeded error (429)
                    if '429' in str(batch_error) or 'Quota exceeded' in str(batch_error) or 'RATE_LIMIT_EXCEEDED' in str(batch_error):
                        print(f"⚠️ Google Sheets API quota exceeded (429) during batch_update. Waiting 65 seconds...")
                        import time
                        time.sleep(65)
                        print(f"🔄 Retrying batch_update after quota cooldown...")
                        try:
                            worksheet.batch_update(updates)
                            print(f"✅ Retry successful! Updated {len(daily_data)} days in Google Sheets ({len(updates)} cells written)")
                        except Exception as retry_error:
                            print(f"❌ Retry also failed: {retry_error}")
                            import traceback
                            traceback.print_exc()
                            raise
                    else:
                        print(f"❌ ERROR in batch_update: {batch_error}")
                        import traceback
                        traceback.print_exc()
                        raise
            else:
                print(f"⚠️ WARNING: No updates to write (updates array is empty)")

            # Calculate and write total reach (итоговый охват)
            if 'reach_column' in column_mapping and column_mapping['reach_column']:
                # OPTIMIZATION: Reuse total_row from earlier section boundary search!
                # total_row was already found when determining section_end_offset
                if not total_row:
                    # Fallback: If somehow not found earlier, search now
                    print(f"⚠️ total_row not cached, searching for 'Всего' row (fallback)...")
                    date_col = column_mapping.get('date_column', 'A')
                    search_range = f"{date_col}{data_start_row}:{date_col}{data_start_row + 50}"
                    search_results = worksheet.get(search_range)

                    for i, row in enumerate(search_results):
                        if row and row[0] and 'всего' in str(row[0]).lower():
                            total_row = data_start_row + i
                            print(f"📍 Found 'Всего' row at: {total_row} (fallback)")
                            break
                else:
                    print(f"✅ Using cached 'Всего' row: {total_row} (saved 1 API call!)")

                if total_row and column_mapping.get('impressions_column'):
                    # Small delay to ensure Google Sheets API has synced the data we just wrote
                    import time
                    time.sleep(0.5)

                    # OPTIMIZATION: Read impressions AND reach in ONE API call using batch_get
                    impressions_col = column_mapping['impressions_column']
                    reach_col = column_mapping['reach_column']

                    impressions_range = f"{impressions_col}{data_start_row}:{impressions_col}{total_row - 1}"
                    reach_range = f"{reach_col}{data_start_row}:{reach_col}{total_row - 1}"

                    print(f"🔍 DEBUG: Reading for total reach calculation:")
                    print(f"   impressions_range: {impressions_range}")
                    print(f"   reach_range: {reach_range}")

                    # Batch get both columns in single API call (saves 1 API call per section!)
                    try:
                        batch_values = worksheet.batch_get([impressions_range, reach_range])
                        impressions_values = batch_values[0] if len(batch_values) > 0 else []
                        reach_values = batch_values[1] if len(batch_values) > 1 else []

                        print(f"   impressions_values length: {len(impressions_values)}")
                        print(f"   reach_values length: {len(reach_values)}")
                        if impressions_values:
                            print(f"   First 3 impressions: {impressions_values[:3]}")
                        if reach_values:
                            print(f"   First 3 reaches: {reach_values[:3]}")
                    except Exception as e:
                        # Check if this is a quota exceeded error (429)
                        if '429' in str(e) or 'Quota exceeded' in str(e) or 'RATE_LIMIT_EXCEEDED' in str(e):
                            print(f"⚠️ Google Sheets API quota exceeded (429). Waiting 65 seconds...")
                            import time
                            time.sleep(65)  # Wait for quota to reset (60 sec + 5 sec buffer)
                            print(f"🔄 Retrying batch_get after quota cooldown...")
                            try:
                                batch_values = worksheet.batch_get([impressions_range, reach_range])
                                impressions_values = batch_values[0] if len(batch_values) > 0 else []
                                reach_values = batch_values[1] if len(batch_values) > 1 else []
                                print(f"✅ Retry successful!")
                            except Exception as retry_error:
                                print(f"❌ Retry also failed: {retry_error}")
                                # If retry fails, skip total reach calculation
                                return True  # Still return success as daily data was written
                        else:
                            print(f"⚠️ batch_get failed: {e}")
                            # For other errors, skip total reach but continue
                            return True

                    # Sum ALL impressions in table
                    total_impressions = 0
                    for row in impressions_values:
                        if row and row[0]:
                            try:
                                # Remove all spaces (including non-breaking spaces \xa0) before converting
                                clean_value = str(row[0]).replace(' ', '').replace('\xa0', '')
                                total_impressions += int(clean_value)
                            except (ValueError, TypeError) as e:
                                print(f"⚠️ Could not parse impression value: '{row[0]}' -> error: {e}")
                                pass

                    # Sum ALL daily reaches in table
                    sum_daily_reaches = 0
                    for row in reach_values:
                        if row and row[0]:
                            try:
                                # Remove all spaces (including non-breaking spaces \xa0) before converting
                                clean_value = str(row[0]).replace(' ', '').replace('\xa0', '')
                                sum_daily_reaches += int(clean_value)
                            except (ValueError, TypeError) as e:
                                print(f"⚠️ Could not parse reach value: '{row[0]}' -> error: {e}")
                                pass

                    # Calculate total reach using total frequency settings (NEW)
                    # Total frequency: random in [total_freq - total_var, total_freq]
                    # This ensures total frequency NEVER exceeds total_frequency!
                    import math

                    # Calculate min and max for total frequency
                    # min = среднее - разбег (например: 2.0 - 0.1 = 1.9)
                    min_total_freq = max(1.0, total_frequency - total_variance)

                    # max = среднее - ε (чуть меньше среднего, НЕ равно)
                    # Это гарантирует что частота НИКОГДА не будет >= среднего
                    max_total_freq = total_frequency - 0.00001

                    # Random total frequency within range [min, max)
                    # Например для частоты 2.0 ± 0.1: диапазон [1.9, 1.99999]
                    actual_total_frequency = random.uniform(min_total_freq, max_total_freq)

                    # Calculate total reach from random total frequency
                    final_total_reach = int(total_impressions / actual_total_frequency) if actual_total_frequency > 0 else 0
                    resulting_frequency = total_impressions / final_total_reach if final_total_reach > 0 else 0

                    # FALLBACK: Если из-за округления int частота >= среднего
                    if resulting_frequency >= total_frequency:
                        print(f"⚠️ Fallback: resulting frequency ({resulting_frequency:.5f}) >= average ({total_frequency})")
                        # Увеличить охват чтобы частота стала < среднего
                        final_total_reach = math.ceil(total_impressions / (total_frequency - 0.001))
                        resulting_frequency = total_impressions / final_total_reach
                        print(f"   Adjusted reach to {final_total_reach:,}, frequency now {resulting_frequency:.5f}")

                    # VALIDATION: Total reach CANNOT be greater than sum of daily reaches
                    # This is physically impossible (total reach = unique users, daily sum includes overlaps)
                    if final_total_reach > sum_daily_reaches:
                        print(f"⚠️ Validation failed: total reach ({final_total_reach:,}) > sum of daily reaches ({sum_daily_reaches:,})")
                        final_total_reach = sum_daily_reaches
                        resulting_frequency = total_impressions / final_total_reach if final_total_reach > 0 else 0
                        print(f"   Corrected: total reach = {final_total_reach:,}, frequency = {resulting_frequency:.5f}")

                    print(f"📊 Total reach calculation (NEW):")
                    print(f"   Total impressions: {total_impressions:,}")
                    print(f"   Total frequency range: {min_total_freq:.2f} - {max_total_freq:.2f} (variance: {total_variance:.2f})")
                    print(f"   Random total frequency: {actual_total_frequency:.5f}")
                    print(f"   Calculated total reach: {total_impressions:,} / {actual_total_frequency:.5f} = {final_total_reach:,}")
                    print(f"   Sum of daily reaches: {sum_daily_reaches:,}")
                    # Protect against division by zero
                    if sum_daily_reaches > 0:
                        percentage = final_total_reach/sum_daily_reaches*100
                        print(f"   Final total reach: {final_total_reach:,} ({percentage:.2f}% of daily sum)")
                    else:
                        print(f"   Final total reach: {final_total_reach:,} (daily sum is 0)")
                    print(f"   ✅ Validation: {final_total_reach} <= {sum_daily_reaches} = {final_total_reach <= sum_daily_reaches}")
                    print(f"   ✅ Resulting frequency: {resulting_frequency:.5f} (max allowed: {max_total_freq:.2f})")

                    # Write total reach to total row
                    total_reach_cell = f"{reach_col}{total_row}"
                    worksheet.update(total_reach_cell, [[final_total_reach]])
                    print(f"✅ Updated total reach in {total_reach_cell}: {final_total_reach}")

            return True

        except Exception as e:
            print(f"❌ Error writing daily data: {e}")
            import traceback
            traceback.print_exc()
            print(f"   Sheet URL: {sheet_url}")
            print(f"   Worksheet: {sheet_name}")
            print(f"   Data start row: {data_start_row}")
            print(f"   Column mapping: {column_mapping}")
            print(f"   Daily data count: {len(daily_data)}")
            return False

    def write_total_report_data(
        self,
        sheet_url: str,
        sheet_name: str,
        campaigns_data: List[Dict],
        id_column: str = 'A',
        reach_column: str = 'C',
        shows_column: str = 'D',
        clicks_column: str = 'E',
        header_row: int = 2,
        frequency_variance: float = 0.1
    ) -> bool:
        """
        Write total report data (summary for period)

        Args:
            sheet_url: Google Sheets URL
            sheet_name: Worksheet name
            campaigns_data: List of dicts with campaign data:
                [{
                    'campaign_id': '282607',
                    'shows': 857894,
                    'clicks': 1386,
                    'frequency': 3.0
                }, ...]
            id_column: Column with campaign IDs (default 'A')
            reach_column: Column for reach (default 'C')
            shows_column: Column for shows (default 'D')
            clicks_column: Column for clicks (default 'E')
            header_row: Row number with headers (default 2)

        Returns:
            bool: True if successful
        """
        if not self.client:
            if not self.authenticate():
                return False

        try:
            sheet_id = self.extract_sheet_id(sheet_url)
            if not sheet_id:
                print(f"❌ Invalid sheet URL: {sheet_url}")
                return False

            spreadsheet = self.client.open_by_key(sheet_id)
            worksheet = spreadsheet.worksheet(sheet_name) if sheet_name else spreadsheet.sheet1

            print(f"\n{'='*60}")
            print(f"📊 TOTAL REPORT: Writing data for {len(campaigns_data)} campaigns")
            print(f"   Sheet: {sheet_name}")
            print(f"   ID column: {id_column}, Reach: {reach_column}, Shows: {shows_column}, Clicks: {clicks_column}")
            print(f"{'='*60}\n")

            # Read entire table to find IDs and detect column structure
            # Read enough rows and columns to cover multiple tables
            all_data = worksheet.get('A1:Z100')

            print(f"📖 Read {len(all_data)} rows from sheet '{sheet_name}'")
            if all_data and len(all_data) > 0:
                print(f"   First row sample: {all_data[0][:10] if len(all_data[0]) > 10 else all_data[0]}")

            # Create mapping: campaign_id -> {row_number, shows_col, clicks_col, reach_col}
            id_to_row_structure = {}

            print(f"🔍 Searching for campaign IDs and column structure...")
            print(f"   Looking for IDs: {[str(c['campaign_id']) for c in campaigns_data]}")

            # Scan all rows to find IDs
            for row_idx, row in enumerate(all_data):
                if not row:
                    continue

                actual_row_num = row_idx + 1

                # Check first few columns for campaign IDs
                for col_idx in range(min(len(row), 20)):  # Check up to column T
                    cell_value = str(row[col_idx]).strip() if row[col_idx] else ""

                    if not cell_value or 'всего' in cell_value.lower():
                        continue

                    # Check if cell contains campaign IDs (6-digit numbers)
                    import re
                    found_ids = re.findall(r'\b(\d{6})\b', cell_value)

                    if not found_ids:
                        continue

                    print(f"   🔍 Row {actual_row_num}, Col {col_idx}: Found IDs {found_ids} in '{cell_value[:50]}'")

                    # Found row with IDs! Now detect column structure
                    # Look for header row (search both above AND below the ID row)
                    header_row_idx = None
                    header_col_start = col_idx

                    # First, search from current row up to beginning of sheet
                    for offset in range(1, row_idx + 1):
                        check_row = row_idx - offset
                        if check_row >= 0 and check_row < len(all_data):
                            check_row_data = all_data[check_row]
                            # Look for header keywords in this row
                            for check_col in range(header_col_start, min(len(check_row_data), header_col_start + 10)):
                                if check_col < len(check_row_data) and check_row_data[check_col]:
                                    cell_text = str(check_row_data[check_col]).lower()
                                    if 'показ' in cell_text or 'клик' in cell_text or 'охват' in cell_text:
                                        header_row_idx = check_row
                                        break
                        if header_row_idx is not None:
                            break

                    # If not found above, search BELOW the ID row (up to 3 rows down)
                    if header_row_idx is None:
                        for offset in range(1, 4):
                            check_row = row_idx + offset
                            if check_row < len(all_data):
                                check_row_data = all_data[check_row]
                                # Look for header keywords in this row
                                for check_col in range(header_col_start, min(len(check_row_data), header_col_start + 10)):
                                    if check_col < len(check_row_data) and check_row_data[check_col]:
                                        cell_text = str(check_row_data[check_col]).lower()
                                        if 'показ' in cell_text or 'клик' in cell_text or 'охват' in cell_text or 'дата' in cell_text:
                                            header_row_idx = check_row
                                            print(f"   ✅ Found header BELOW ID row at row {check_row + 1}")
                                            break
                            if header_row_idx is not None:
                                break

                    if header_row_idx is None:
                        print(f"   ⚠️ No header found for IDs at row {actual_row_num} (searched above and below), skipping")
                        continue

                    # Parse header row to find column positions
                    header_row_data = all_data[header_row_idx]

                    def col_idx_to_letter(idx):
                        result = ''
                        while idx >= 0:
                            result = chr(65 + (idx % 26)) + result
                            idx = idx // 26 - 1
                        return result

                    shows_col = None
                    clicks_col = None
                    reach_col = None

                    # Search in range around the ID column
                    search_start = max(0, header_col_start - 1)
                    search_end = min(len(header_row_data), header_col_start + 10)

                    for h_col in range(search_start, search_end):
                        if h_col < len(header_row_data) and header_row_data[h_col]:
                            header_text = str(header_row_data[h_col]).lower()

                            if 'показ' in header_text and not shows_col:
                                shows_col = col_idx_to_letter(h_col)
                            elif 'клик' in header_text and not clicks_col:
                                clicks_col = col_idx_to_letter(h_col)
                            elif 'охват' in header_text and not reach_col:
                                reach_col = col_idx_to_letter(h_col)

                    # Store structure for each ID in this row
                    # Find "Всего" row below this section (search up to 50 rows down)
                    total_row = None
                    for search_offset in range(1, 50):
                        search_row_idx = row_idx + search_offset
                        if search_row_idx < len(all_data):
                            search_row = all_data[search_row_idx]
                            if search_row and len(search_row) > col_idx:
                                cell_text = str(search_row[col_idx]).lower().strip()
                                if 'всего' in cell_text:
                                    total_row = search_row_idx + 1  # Convert to 1-based row number
                                    print(f"   ✅ Found 'Всего' row at {total_row} (below ID row)")
                                    break

                    # If "Всего" not found, use ID row as fallback
                    target_row = total_row if total_row else actual_row_num

                    for single_id in found_ids:
                        id_to_row_structure[single_id] = {
                            'row': target_row,  # Use "Всего" row if found, otherwise ID row
                            'id_row': actual_row_num,  # Store original ID row for reference
                            'shows_col': shows_col,
                            'clicks_col': clicks_col,
                            'reach_col': reach_col
                        }

                    print(f"   ✅ Found IDs {found_ids} at row {actual_row_num}")
                    print(f"      Target row for data: {target_row} {'(Всего row)' if total_row else '(ID row - fallback)'}")
                    print(f"      Shows: {shows_col}, Clicks: {clicks_col}, Reach: {reach_col}")

            print(f"\n📋 Total: {len(id_to_row_structure)} campaign IDs found with structure")

            # Group campaigns by row AND column location (multiple tables can have same row number)
            # Use (row_num, shows_col, clicks_col) as unique key for each table cell
            row_aggregated_data = {}

            for campaign_data in campaigns_data:
                campaign_id = str(campaign_data['campaign_id'])
                shows = campaign_data['shows']
                clicks = campaign_data['clicks']
                # Use pre-calculated average reach from daily data
                reach = campaign_data.get('average_reach', 0)

                # Find row and structure for this campaign
                if campaign_id not in id_to_row_structure:
                    print(f"⚠️  Campaign ID {campaign_id} not found in table, skipping")
                    continue

                structure = id_to_row_structure[campaign_id]
                row_num = structure['row']
                shows_col = structure['shows_col']
                clicks_col = structure['clicks_col']
                reach_col = structure['reach_col']

                print(f"📝 Campaign {campaign_id}: Shows={shows:,}, Clicks={clicks:,}, Avg Reach={reach:,} → Row {row_num}, Cols {shows_col}/{clicks_col}")

                # Create unique key for this table cell: (row, shows_col, clicks_col)
                # This prevents mixing data from different tables with same row number
                cell_key = (row_num, shows_col, clicks_col, reach_col)

                # Aggregate data for this cell
                if cell_key not in row_aggregated_data:
                    row_aggregated_data[cell_key] = {
                        'shows': 0,
                        'clicks': 0,
                        'reach': 0,
                        'structure': structure,
                        'campaign_ids': []
                    }

                row_aggregated_data[cell_key]['shows'] += shows
                row_aggregated_data[cell_key]['clicks'] += clicks
                row_aggregated_data[cell_key]['reach'] += reach  # Sum of average reaches
                row_aggregated_data[cell_key]['campaign_ids'].append(campaign_id)

            # Now write aggregated data (one update per unique cell)
            updates_made = 0
            for cell_key, data in row_aggregated_data.items():
                row_num, shows_col, clicks_col, reach_col = cell_key

                total_shows = data['shows']
                total_clicks = data['clicks']
                total_reach = data['reach']

                print(f"\n📊 Writing to row {row_num}, cols {shows_col}/{clicks_col} (campaigns: {', '.join(data['campaign_ids'])}):")
                print(f"   Total Shows: {total_shows:,}, Clicks: {total_clicks:,}, Reach: {total_reach:,}")
                print(f"   Columns: Shows={shows_col}, Clicks={clicks_col}, Reach={reach_col}")

                # Prepare updates for this row
                updates = []

                if shows_col:
                    updates.append({
                        'range': f'{shows_col}{row_num}',
                        'values': [[total_shows]]
                    })

                if clicks_col:
                    updates.append({
                        'range': f'{clicks_col}{row_num}',
                        'values': [[total_clicks]]
                    })

                if reach_col and total_reach > 0:
                    updates.append({
                        'range': f'{reach_col}{row_num}',
                        'values': [[total_reach]]
                    })

                # Write all updates for this cell
                if updates:
                    worksheet.batch_update(updates)
                    updates_made += 1
                    print(f"   ✅ Updated row {row_num}, cols {shows_col}/{clicks_col} with {len(updates)} values")
                else:
                    print(f"   ⚠️ No columns found to update for row {row_num}, cols {shows_col}/{clicks_col}")

            print(f"\n✅ Total report complete: {updates_made}/{len(campaigns_data)} campaigns updated")
            return True

        except Exception as e:
            print(f"❌ Error writing total report: {e}")
            import traceback
            traceback.print_exc()
            return False

    def write_video_detailed_data(
        self,
        sheet_url: str,
        sheet_name: str,
        campaigns_daily_data: List[Dict],
        header_row: int = 2,
        data_start_row: int = 3,
        frequency_variance: float = 0.1
    ) -> bool:
        """
        Write detailed video report data (Realweb custom format)
        Each row = 1 day × 1 campaign with all video completion metrics

        Format:
        Дата | ID Кампании | Название кампании | Показы | Охват | Клики | CTR |
        Досмотры 25% | Досмотры 50% | Досмотры 75% | Досмотры 100% | VTR | Потрачено

        Args:
            sheet_url: Google Sheets URL
            sheet_name: Worksheet name
            campaigns_daily_data: List of dicts with campaign + daily data:
                [{
                    'campaign_id': '282607',
                    'campaign_name': 'Campaign Name',
                    'frequency': 3.0,
                    'daily_data': [
                        {
                            'date': '15.04.2026',
                            'impressions': 217116,
                            'clicks': 476,
                            'ctr': 0.22,
                            'vast25': 50000,
                            'vast50': 40000,
                            'vast75': 30000,
                            'vastComplete': 20000,
                            'vtr': 9.21,
                            'spent': 15000.50
                        },
                        ...
                    ]
                }, ...]
            header_row: Row with headers (default 2)
            data_start_row: First data row (default 3)

        Returns:
            bool: True if successful
        """
        if not self.client:
            if not self.authenticate():
                return False

        try:
            sheet_id = self.extract_sheet_id(sheet_url)
            if not sheet_id:
                print(f"❌ Invalid sheet URL: {sheet_url}")
                return False

            spreadsheet = self.client.open_by_key(sheet_id)
            worksheet = spreadsheet.worksheet(sheet_name) if sheet_name else spreadsheet.sheet1

            print(f"\n{'='*60}")
            print(f"📊 REALWEB VIDEO DETAILED REPORT")
            print(f"   Sheet: {sheet_name}")
            print(f"   Campaigns: {len(campaigns_daily_data)}")
            print(f"{'='*60}\n")

            # Prepare all rows to write
            rows_to_write = []
            rows_with_dates = []  # Temporary list with dates for sorting

            for campaign_data in campaigns_daily_data:
                campaign_id = campaign_data['campaign_id']
                campaign_name = campaign_data['campaign_name']
                format_type = campaign_data.get('format_type', 'B')  # B/V/CTV/TGB
                frequency = campaign_data.get('frequency', 3.0)
                daily_data = campaign_data['daily_data']

                print(f"📝 Processing campaign {campaign_id} ({campaign_name}): {len(daily_data)} days, Type: {format_type}")

                # DEBUG: Print first day to check video metrics
                if len(daily_data) > 0:
                    first_day = daily_data[0]
                    print(f"   🔍 First day check: vast25={first_day.get('vast25', 'MISSING')}, vast50={first_day.get('vast50', 'MISSING')}, vastComplete={first_day.get('vastComplete', 'MISSING')}")

                for day_data in daily_data:
                    impressions = day_data.get('impressions', 0)

                    # Calculate reach with random frequency variation
                    min_freq = max(1.0, frequency - frequency_variance)
                    actual_frequency = random.uniform(min_freq, frequency)
                    reach = int(impressions / actual_frequency) if impressions > 0 else 0

                    # Check if this is CTV campaign (Connected TV - no clicks)
                    is_ctv = format_type == 'CTV'

                    # Prepare row data
                    row = [
                        day_data.get('date', ''),                    # Дата
                        campaign_id,                                  # ID Кампании
                        campaign_name,                                # Название кампании
                        impressions,                                  # Показы
                        reach,                                        # Охват
                        '' if is_ctv else day_data.get('clicks', 0), # Клики (пусто для CTV)
                        '',                                           # CTR - оставляем пустым для формулы
                        day_data.get('vast25', 0),                   # Досмотры 25%
                        day_data.get('vast50', 0),                   # Досмотры 50%
                        day_data.get('vast75', 0),                   # Досмотры 75%
                        day_data.get('vastComplete', 0),             # Досмотры 100%
                        '',                                           # VTR - оставляем пустым для формулу
                        day_data.get('spent', 0)                     # Потрачено
                    ]

                    # Add row with date_iso for sorting
                    rows_with_dates.append({
                        'date_iso': day_data.get('date_iso', day_data.get('date', '')),
                        'row': row
                    })

            # Sort all rows by date (ascending: 23.04, 24.04, 25.04...)
            rows_with_dates.sort(key=lambda x: x['date_iso'])
            rows_to_write = [item['row'] for item in rows_with_dates]

            print(f"📊 Total rows to write: {len(rows_to_write)}")

            if not rows_to_write:
                print("⚠️ No data to write")
                return False

            # APPEND MODE: Find last row and add new data after it
            # Read existing data to find where to append
            existing_range = f"A{data_start_row}:M{data_start_row + 1000}"
            existing_data = worksheet.get(existing_range)

            # Find last non-empty row
            last_row = data_start_row - 1
            for i, row in enumerate(existing_data):
                if row and any(cell for cell in row):
                    last_row = data_start_row + i

            print(f"📍 Last existing row: {last_row}")

            # Start writing AFTER last row
            append_start_row = last_row + 1

            # Write all data at once (batch append)
            write_range = f"A{append_start_row}:M{append_start_row + len(rows_to_write) - 1}"
            worksheet.update(write_range, rows_to_write, value_input_option='USER_ENTERED')

            print(f"✅ Successfully ADDED {len(rows_to_write)} new rows to {write_range}")
            print(f"   Previous data preserved. New data starts at row {append_start_row}")
            print(f"   Format: Date | ID | Name | Shows | Reach | Clicks | CTR | 25% | 50% | 75% | 100% | VTR | Spent")

            return True

        except Exception as e:
            print(f"❌ Error writing video detailed data: {e}")
            import traceback
            traceback.print_exc()
            return False

    def test_access(self, sheet_url: str) -> bool:
        """
        Test if we have access to the spreadsheet

        Args:
            sheet_url: Google Sheets URL

        Returns:
            bool: True if accessible
        """
        if not self.client:
            if not self.authenticate():
                return False

        try:
            sheet_id = self.extract_sheet_id(sheet_url)
            if not sheet_id:
                return False

            spreadsheet = self.client.open_by_key(sheet_id)
            return True

        except Exception as e:
            print(f"Access test failed: {e}")
            return False
