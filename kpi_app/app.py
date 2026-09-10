#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
KPI Dashboard - веб-интерфейс для работы с KPI метриками из Google Sheets
"""

from flask import Flask, render_template, request, jsonify
import logging
from kpi_parser import parse_kpi_campaigns, search_campaigns

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False


@app.route('/')
def index():
    """Главная страница с интерфейсом поиска KPI"""
    return render_template('index.html')


@app.route('/api/kpi/search', methods=['POST'])
def search_kpi():
    """
    Поиск кампаний в KPI таблице

    Параметры:
    - account: название аккаунта (частичное совпадение)
    - campaign_id: ID кампании (точное совпадение)
    - campaign_name: название кампании (частичное совпадение)
    - url: опционально - URL Google Sheets таблицы
    """
    try:
        data = request.get_json()
        account = data.get('account', '').strip()
        campaign_id = data.get('campaign_id', '').strip()
        campaign_name = data.get('campaign_name', '').strip()
        sheet_url = data.get('url', '').strip()

        logger.info(f"KPI поиск: account={account}, campaign_id={campaign_id}, campaign_name={campaign_name}")

        # Загружаем все кампании из KPI таблицы
        all_campaigns = parse_kpi_campaigns(url=sheet_url if sheet_url else None)

        # Применяем фильтры поиска
        results = search_campaigns(
            all_campaigns,
            account=account if account else None,
            campaign_id=campaign_id if campaign_id else None,
            campaign_name=campaign_name if campaign_name else None
        )

        logger.info(f"Найдено кампаний: {len(results)}")

        return jsonify({
            'success': True,
            'campaigns': results,
            'total': len(results)
        })

    except Exception as e:
        logger.error(f"Ошибка поиска KPI: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/kpi/all', methods=['GET'])
def get_all_campaigns():
    """Получить все кампании из KPI таблицы"""
    try:
        sheet_url = request.args.get('url', '').strip()

        logger.info("Загрузка всех кампаний из KPI таблицы")

        all_campaigns = parse_kpi_campaigns(url=sheet_url if sheet_url else None)

        logger.info(f"Загружено кампаний: {len(all_campaigns)}")

        return jsonify({
            'success': True,
            'campaigns': all_campaigns,
            'total': len(all_campaigns)
        })

    except Exception as e:
        logger.error(f"Ошибка загрузки кампаний: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)
