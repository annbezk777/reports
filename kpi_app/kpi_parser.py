#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Парсер KPI таблиц из Google Sheets

Поддерживает специфическую структуру KPI таблиц:
- Каждая кампания имеет несколько строк: План, за всю рк, неделя 1-5
- Поддержка множественных ID кампаний в одной строке
- Извлечение метрик: визиты, отказы, глубина, время, роботность, PI
"""

import re
import csv
import logging
import requests
from io import StringIO
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# URL тестовой KPI таблицы
DEFAULT_KPI_URL = "https://docs.google.com/spreadsheets/d/1aIcL9bQR2FPI2VIdXS5ZRbRFpE8bEayJfBx5dbkr8Yo/edit?gid=889950758#gid=889950758"

# Индексы столбцов KPI таблицы (0-based)
# Реальная структура: Sales, ?, ?, Account, AdOps, РК, клики, визиты, отказы, глубина, время, роб, PI
COL_SALES = 0  # Может содержать ID РК или имя менеджера
COL_ACCOUNT = 3  # Название аккаунта/кампании
COL_ADOPS = 4  # Менеджер
COL_RK = 5  # Тип строки (План, за всю рк, неделя 1, и т.д.)
COL_CLICKS = 6
COL_VISITS = 7
COL_BOUNCES = 8
COL_DEPTH = 9
COL_TIME = 10
COL_ROBOTNESS = 11
COL_PI = 12


def safe_float(value):
    """Безопасное преобразование в float"""
    if not value or value == '' or value == '#DIV/0!' or value == '-':
        return 0.0
    try:
        value = str(value).strip().replace(' ', '').replace(',', '.').replace('%', '')
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def safe_int(value):
    """Безопасное преобразование в int"""
    if not value or value == '' or value == '#DIV/0!' or value == '-':
        return 0
    try:
        return int(str(value).strip().replace(' ', ''))
    except (ValueError, TypeError):
        return 0


def parse_sheet_url(url: str) -> tuple:
    """Извлекает ID таблицы и gid листа из URL"""
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', url)
    if not match:
        raise ValueError("Неверный формат URL Google Таблицы")

    sheet_id = match.group(1)
    gid_match = re.search(r'[?#&]gid=(\d+)', url)
    gid = gid_match.group(1) if gid_match else '0'

    return sheet_id, gid


def load_sheet_as_csv(sheet_id: str, gid: str = '0') -> str:
    """Загружает лист Google Таблицы в формате CSV"""
    export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"

    try:
        response = requests.get(export_url, allow_redirects=True, timeout=10)
        response.raise_for_status()
        response.encoding = 'utf-8'
        return response.text
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка загрузки Google Таблицы: {e}")
        raise Exception(f"Не удалось загрузить таблицу: {e}")


def extract_campaign_ids(text: str) -> List[str]:
    """
    Извлекает ID кампаний из текста

    Примеры:
    - "ID РК 298270" -> ["298270"]
    - "ID РК 298270 297426 297425" -> ["298270", "297426", "297425"]
    - "298270" -> ["298270"]
    """
    if not text:
        return []

    # Убираем текст "ID РК" если есть
    text = text.replace('ID РК', '').replace('ID', '').strip()

    # Ищем все числа (ID кампаний)
    ids = re.findall(r'\d{6,}', text)
    return ids


def is_plan_row(text: str) -> bool:
    """Проверяет является ли строка строкой плана"""
    if not text:
        return False
    text_lower = text.lower().strip()
    return 'план' in text_lower or text_lower == 'план'


def is_fact_row(text: str) -> bool:
    """Проверяет является ли строка строкой факта 'за всю рк'"""
    if not text:
        return False
    text_lower = text.lower().strip()
    return 'за всю' in text_lower or 'факт' in text_lower


def is_week_row(text: str) -> Optional[str]:
    """
    Проверяет является ли строка строкой недели
    Возвращает название недели если да, иначе None
    """
    if not text:
        return None

    text_lower = text.lower().strip()

    # Ищем паттерны типа "неделя 1", "1-8", "9-15" и т.д.
    week_patterns = [
        r'неделя\s*(\d+)',
        r'(\d{1,2})\s*-\s*(\d{1,2})',
        r'нед\.?\s*(\d+)'
    ]

    for pattern in week_patterns:
        match = re.search(pattern, text_lower)
        if match:
            if len(match.groups()) == 2:
                # Паттерн с диапазоном (1-8)
                return f"{match.group(1)}-{match.group(2)}"
            else:
                # Паттерн с номером недели
                return f"Неделя {match.group(1)}"

    return None


def parse_kpi_campaigns(url: str = None) -> List[Dict]:
    """
    Парсит KPI таблицу и возвращает список кампаний с метриками

    Структура возвращаемых данных:
    [
        {
            'name': 'Название кампании',
            'account': 'Account',
            'manager': 'Менеджер',
            'campaign_ids': ['298270', '297426'],
            'plan': {...},
            'fact': {...},
            'weeks': [...]
        }
    ]
    """
    if not url:
        url = DEFAULT_KPI_URL

    logger.info(f"Парсинг KPI таблицы: {url}")

    # Загружаем таблицу
    sheet_id, gid = parse_sheet_url(url)
    csv_content = load_sheet_as_csv(sheet_id, gid)

    # Парсим CSV
    reader = csv.reader(StringIO(csv_content))
    rows = list(reader)

    if len(rows) < 2:
        raise ValueError("Таблица пустая или содержит только заголовки")

    campaigns = []
    current_campaign = None

    # Пропускаем первые 4 строки (заголовки и бенчмарки)
    for i, row in enumerate(rows[4:], start=4):
        if len(row) < COL_VISITS:
            continue

        sales_col = row[COL_SALES].strip() if len(row) > COL_SALES else ''
        account = row[COL_ACCOUNT].strip() if len(row) > COL_ACCOUNT else ''
        adops = row[COL_ADOPS].strip() if len(row) > COL_ADOPS else ''
        rk_text = row[COL_RK].strip() if len(row) > COL_RK else ''

        # Пропускаем строки с #REF! или полностью пустые
        if '#REF!' in sales_col or '#REF!' in account:
            continue

        if not sales_col and not account and not adops and not rk_text:
            continue

        # Извлекаем метрики из строки
        metrics = {
            'clicks': safe_int(row[COL_CLICKS] if len(row) > COL_CLICKS else ''),
            'visits': safe_int(row[COL_VISITS] if len(row) > COL_VISITS else ''),
            'bounces': safe_float(row[COL_BOUNCES] if len(row) > COL_BOUNCES else ''),
            'depth': safe_float(row[COL_DEPTH] if len(row) > COL_DEPTH else ''),
            'time': safe_int(row[COL_TIME] if len(row) > COL_TIME else ''),
            'robotness': safe_float(row[COL_ROBOTNESS] if len(row) > COL_ROBOTNESS else ''),
            'pi': safe_float(row[COL_PI] if len(row) > COL_PI else '')
        }

        # Проверяем есть ли ID кампаний в первом столбце
        campaign_ids = extract_campaign_ids(sales_col)

        # Определяем тип строки
        is_plan = is_plan_row(rk_text)
        is_fact = is_fact_row(rk_text)
        week_name = is_week_row(account) or is_week_row(rk_text)  # Проверяем и account и rk_text

        # Начало новой кампании: есть имя в sales_col, есть название в account, но account != "Неделя"
        is_campaign_start = (sales_col and account and
                            account.lower() not in ['неделя', 'week'] and
                            not week_name and
                            'id рк' not in sales_col.lower())

        if is_campaign_start:
            # Сохраняем предыдущую кампанию если есть
            if current_campaign:
                campaigns.append(current_campaign)

            # Создаем новую кампанию
            current_campaign = {
                'name': account,
                'account': account,
                'manager': sales_col,  # В первой строке кампании - имя менеджера
                'campaign_ids': [],
                'plan': metrics,  # Первая строка - это план
                'fact': {},
                'weeks': []
            }

        # Строка с ID кампаний
        elif campaign_ids and current_campaign:
            current_campaign['campaign_ids'] = campaign_ids

        # Обрабатываем строки факта и недель если уже есть кампания
        elif current_campaign:
            if is_fact:
                current_campaign['fact'] = metrics
            elif week_name:
                # Проверяем что это не строка заголовка недель
                if account.lower() not in ['неделя', 'week']:
                    current_campaign['weeks'].append({
                        'name': week_name,
                        **metrics
                    })

    # Добавляем последнюю кампанию
    if current_campaign:
        campaigns.append(current_campaign)

    logger.info(f"Найдено кампаний: {len(campaigns)}")
    return campaigns


def search_campaigns(campaigns: List[Dict], account: str = None, campaign_id: str = None, campaign_name: str = None) -> List[Dict]:
    """
    Ищет кампании по заданным критериям

    Args:
        campaigns: Список кампаний
        account: Название аккаунта (частичное совпадение, case-insensitive)
        campaign_id: ID кампании (точное совпадение)
        campaign_name: Название кампании (частичное совпадение, case-insensitive)

    Returns:
        Список найденных кампаний
    """
    results = []

    for campaign in campaigns:
        match = True

        # Фильтр по account
        if account:
            account_lower = account.lower()
            campaign_account = campaign.get('account', '').lower()
            if account_lower not in campaign_account:
                match = False

        # Фильтр по campaign_id
        if campaign_id and match:
            campaign_ids = campaign.get('campaign_ids', [])
            if campaign_id not in campaign_ids:
                match = False

        # Фильтр по campaign_name
        if campaign_name and match:
            name_lower = campaign_name.lower()
            campaign_name_text = campaign.get('name', '').lower()
            if name_lower not in campaign_name_text:
                match = False

        if match:
            results.append(campaign)

    return results


# Тестирование
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    try:
        campaigns = parse_kpi_campaigns()
        print(f"\nНайдено кампаний: {len(campaigns)}")

        for camp in campaigns[:3]:
            print(f"\n{camp['name']}")
            print(f"  Account: {camp['account']}")
            print(f"  Manager: {camp['manager']}")
            print(f"  IDs: {', '.join(camp['campaign_ids'])}")
            print(f"  План - Визиты: {camp['plan'].get('visits', 0)}")
            print(f"  Факт - Визиты: {camp['fact'].get('visits', 0)}")
            print(f"  Недель: {len(camp['weeks'])}")

        # Тест поиска
        print("\n\n=== Тест поиска ===")
        if campaigns:
            test_id = campaigns[0]['campaign_ids'][0] if campaigns[0]['campaign_ids'] else None
            if test_id:
                results = search_campaigns(campaigns, campaign_id=test_id)
                print(f"Поиск по ID {test_id}: найдено {len(results)} кампаний")

    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
