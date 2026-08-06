#!/usr/bin/env python3
"""
Test: Read Stroydvor sheet and check IDs
"""
import sys
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from app.api.google_sheets_client import GoogleSheetsClient
from config import Config
import re

# Initialize
gs_client = GoogleSheetsClient(
    credentials_file=Config.GOOGLE_CREDENTIALS_FILE,
    scopes=Config.GOOGLE_SCOPES
)

if not gs_client.authenticate():
    print("❌ Auth failed")
    sys.exit(1)

# Read Stroydvor sheet
sheet_url = "https://docs.google.com/spreadsheets/d/1V3fLZ5_DaW1FqRNKznk8eCLm_aTRlXN4xxSqHSr7xvY/edit"
sheet_name = "Тотал по ГЕО(01-30.06)"

sheet_id = gs_client.extract_sheet_id(sheet_url)
spreadsheet = gs_client.client.open_by_key(sheet_id)
worksheet = spreadsheet.worksheet(sheet_name)

print(f"📖 Reading sheet: {sheet_name}")
all_data = worksheet.get('A1:G15')

print(f"\n📋 First 15 rows:")
for i, row in enumerate(all_data[:15], 1):
    if row:
        print(f"Row {i}: {row[:5] if len(row) > 5 else row}")

print(f"\n🔍 Searching for campaign IDs (6-digit numbers):")
for row_idx, row in enumerate(all_data):
    if not row:
        continue

    actual_row = row_idx + 1

    for col_idx in range(min(len(row), 5)):
        cell_value = str(row[col_idx]).strip() if row[col_idx] else ""

        if not cell_value:
            continue

        # Find 6-digit IDs
        found_ids = re.findall(r'\b(\d{6})\b', cell_value)

        if found_ids:
            print(f"   Row {actual_row}, Col {col_idx}: '{cell_value}' → IDs: {found_ids}")

print("\n✅ Done")
