#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Parse Adriver Excel exports and extract IVT data
"""

import sys
import os
import xml.etree.ElementTree as ET
import zipfile
import tempfile
import re

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from flask import Flask
from config import Config
from app.models import db, MonitoringCampaign

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)


class AdriverExcelParser:
    """Parse Adriver Excel statistics export"""

    def __init__(self, excel_file_path):
        self.excel_file_path = excel_file_path
        self.temp_dir = None

    def parse(self):
        """
        Parse Excel file and extract IVT data

        Returns:
            dict with IVT statistics
        """
        print(f"📂 Parsing Adriver Excel: {os.path.basename(self.excel_file_path)}\n")

        # Create temp directory
        self.temp_dir = tempfile.mkdtemp()

        try:
            # Extract xlsx (it's a zip file)
            with zipfile.ZipFile(self.excel_file_path, 'r') as zip_ref:
                zip_ref.extractall(self.temp_dir)

            # Parse XML files
            worksheet_path = os.path.join(self.temp_dir, 'xl', 'worksheets', 'sheet1.xml')
            strings_path = os.path.join(self.temp_dir, 'xl', 'sharedStrings.xml')

            # Parse shared strings
            strings_tree = ET.parse(strings_path)
            strings_root = strings_tree.getroot()

            shared_strings = []
            for si in strings_root.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t'):
                shared_strings.append(si.text if si.text else '')

            # Parse worksheet
            tree = ET.parse(worksheet_path)
            root = tree.getroot()

            ns = {'ss': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            rows = root.findall('.//ss:row', ns)

            # Find header row
            header_row_idx = self._find_header_row(rows, shared_strings, ns)

            if header_row_idx is None:
                print("❌ Could not find header row")
                return None

            # Get headers
            headers = self._get_row_values(rows[header_row_idx], shared_strings, ns)

            print(f"📋 Found {len(headers)} columns\n")

            # Find "Всего" (Total) row
            total_row_idx = self._find_total_row(rows, shared_strings, ns)

            if total_row_idx is None:
                print("❌ Could not find 'Всего' row")
                return None

            # Parse total row
            total_values = self._get_row_values(rows[total_row_idx], shared_strings, ns)

            # Map headers to values
            data = dict(zip(headers, total_values))

            # Extract IVT data
            ivt_data = self._extract_ivt_data(data)

            return ivt_data

        finally:
            # Cleanup temp directory
            import shutil
            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)

    def _find_header_row(self, rows, shared_strings, ns):
        """Find row with column headers"""
        for i, row in enumerate(rows):
            cells = row.findall('.//ss:c', ns)
            if cells:
                first_cell = self._get_cell_value(cells[0], shared_strings, ns)
                if 'дата' in str(first_cell).lower():
                    return i
        return None

    def _find_total_row(self, rows, shared_strings, ns):
        """Find row with 'Всего' (Total)"""
        for i, row in enumerate(rows):
            cells = row.findall('.//ss:c', ns)
            if cells:
                first_cell = self._get_cell_value(cells[0], shared_strings, ns)
                if first_cell and 'всего' in str(first_cell).lower():
                    return i
        return None

    def _get_cell_value(self, cell, shared_strings, ns):
        """Get value from cell"""
        t = cell.get('t')
        v_elem = cell.find('.//ss:v', ns)
        if v_elem is not None:
            if t == 's':  # shared string
                idx = int(v_elem.text)
                return shared_strings[idx] if idx < len(shared_strings) else ''
            else:
                return v_elem.text
        return ''

    def _get_row_values(self, row, shared_strings, ns):
        """Get all values from a row"""
        cells = row.findall('.//ss:c', ns)
        values = []
        for cell in cells:
            value = self._get_cell_value(cell, shared_strings, ns)
            values.append(value)
        return values

    def _parse_number(self, text):
        """Parse number from text"""
        if not text:
            return 0
        # Remove spaces, commas, non-breaking spaces
        text = str(text).replace(' ', '').replace(',', '').replace('\xa0', '').replace('\u00a0', '')
        try:
            return int(float(text))
        except:
            return 0

    def _parse_percent(self, text):
        """Parse percentage"""
        if not text:
            return 0.0
        # Remove %, replace comma with dot
        text = str(text).replace('%', '').replace(',', '.').replace(' ', '')
        try:
            return float(text)
        except:
            return 0.0

    def _extract_ivt_data(self, data):
        """Extract IVT data from parsed row"""
        print("📊 Extracted IVT Data:\n")

        # Раздел 3.2 ТЗ по верификаторам: сравниваем SAPE с сырыми
        # (не очищенными от IVT) показами/кликами Adriver - берём колонку
        # "...всего с учетом IVT", а не просто "Показы"/"Клики" (которая
        # в части выгрузок Adriver вообще не встречается под таким именем).
        ivt_data = {
            'impressions': self._parse_number(data.get('Показов всего с учетом IVT', data.get('Показы', 0))),
            'clicks': self._parse_number(data.get('Кликов всего с учетом IVT', data.get('Клики', 0))),
            'ivt_impressions': self._parse_number(data.get('Показы IVT', 0)),
            'ivt_impressions_percent': self._parse_percent(data.get('Показы %IVT', 0)),
            'givt_impressions': self._parse_number(data.get('Показы GIVT', 0)),
            'givt_impressions_percent': self._parse_percent(data.get('Показы %GIVT', 0)),
            'sivt_impressions': self._parse_number(data.get('Показы SIVT', 0)),
            'sivt_impressions_percent': self._parse_percent(data.get('Показы %SIVT', 0)),
            'ivt_clicks': self._parse_number(data.get('Клики IVT', 0)),
            'ivt_clicks_percent': self._parse_percent(data.get('Клики %IVT', 0)),
            'givt_clicks': self._parse_number(data.get('Клики GIVT', 0)),
            'givt_clicks_percent': self._parse_percent(data.get('Клики %GIVT', 0)),
            'sivt_clicks': self._parse_number(data.get('Клики SIVT', 0)),
            'sivt_clicks_percent': self._parse_percent(data.get('Клики %SIVT', 0)),
        }

        # Print results
        for key, value in ivt_data.items():
            if 'percent' in key:
                print(f"  {key}: {value}%")
            else:
                print(f"  {key}: {value:,}")

        return ivt_data


def test_parse():
    """Test parsing"""
    file_path = '/Users/annabereznyak/Downloads/AdriverStat_ID_ 844475_days_01-10-26_10-10-26.xlsx'

    parser = AdriverExcelParser(file_path)
    ivt_data = parser.parse()

    if ivt_data:
        print("\n" + "="*60)
        print("✅ Successfully parsed IVT data!")
        print("="*60)
    else:
        print("\n❌ Failed to parse")


if __name__ == '__main__':
    test_parse()
