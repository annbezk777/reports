#!/usr/bin/env python3
"""
Migration script: Convert old frequency structure to new campaign_settings format

OLD:
  campaign_frequencies: {"1": 3.0, "2": 4.0}
  frequency_variance: 0.1
  total_reach_coefficient: 0.96

NEW:
  campaign_settings: {
    "1": {
      "daily_frequency": 3.0,
      "daily_variance": 0.1,
      "total_frequency": 3.0,
      "total_variance": 0.1
    }
  }
"""

import sqlite3
import json
import sys

DATABASE_PATH = 'database/sape_reports.db'

def migrate():
    print("="*80)
    print("МИГРАЦИЯ: Переход на новую структуру campaign_settings")
    print("="*80)

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # 1. Add new column if not exists
    print("\n1️⃣ Добавление колонки campaign_settings...")
    try:
        cursor.execute("ALTER TABLE report_configs ADD COLUMN campaign_settings JSON")
        print("   ✅ Колонка campaign_settings добавлена")
    except sqlite3.OperationalError as e:
        if 'duplicate column name' in str(e).lower():
            print("   ℹ️  Колонка campaign_settings уже существует")
        else:
            raise

    # 2. Get all reports with old structure
    print("\n2️⃣ Поиск отчетов для миграции...")
    cursor.execute("""
        SELECT id, name, campaign_frequencies, frequency_variance, total_reach_coefficient
        FROM report_configs
        WHERE campaign_settings IS NULL
          AND campaign_frequencies IS NOT NULL
    """)

    reports_to_migrate = cursor.fetchall()
    print(f"   Найдено отчетов для миграции: {len(reports_to_migrate)}")

    if len(reports_to_migrate) == 0:
        print("   ✅ Нет отчетов для миграции (все уже обновлены)")
        conn.close()
        return

    # 3. Migrate each report
    print("\n3️⃣ Миграция данных...")
    migrated_count = 0
    errors = []

    for report_id, report_name, campaign_freqs_json, freq_variance, total_coef in reports_to_migrate:
        try:
            # Parse old data
            campaign_frequencies = json.loads(campaign_freqs_json) if campaign_freqs_json else {}

            if not campaign_frequencies:
                print(f"   ⚠️  Report {report_id} ({report_name}): пропущен (нет частот)")
                continue

            # Build new structure
            campaign_settings = {}
            for campaign_id, daily_freq in campaign_frequencies.items():
                campaign_settings[campaign_id] = {
                    "daily_frequency": daily_freq,
                    "daily_variance": freq_variance if freq_variance is not None else 0.1,
                    "total_frequency": daily_freq,  # По умолчанию = дневной
                    "total_variance": 0.1  # По умолчанию 0.1
                }

            # Update report
            cursor.execute("""
                UPDATE report_configs
                SET campaign_settings = ?
                WHERE id = ?
            """, (json.dumps(campaign_settings), report_id))

            migrated_count += 1
            print(f"   ✅ Report {report_id} ({report_name}): мигрировано {len(campaign_settings)} кампаний")

        except Exception as e:
            error_msg = f"Report {report_id} ({report_name}): {str(e)}"
            errors.append(error_msg)
            print(f"   ❌ {error_msg}")

    # 4. Commit changes
    if migrated_count > 0:
        conn.commit()
        print(f"\n4️⃣ ✅ Успешно мигрировано: {migrated_count} отчетов")

    if errors:
        print(f"\n⚠️  Ошибки при миграции ({len(errors)}):")
        for err in errors:
            print(f"   - {err}")

    # 5. Verification
    print("\n5️⃣ Проверка результатов...")
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN campaign_settings IS NOT NULL THEN 1 ELSE 0 END) as with_new,
            SUM(CASE WHEN campaign_frequencies IS NOT NULL THEN 1 ELSE 0 END) as with_old
        FROM report_configs
    """)
    total, with_new, with_old = cursor.fetchone()

    print(f"   Всего отчетов: {total}")
    print(f"   С campaign_settings: {with_new}")
    print(f"   С campaign_frequencies (старый формат): {with_old}")

    # Show example
    cursor.execute("""
        SELECT id, name, campaign_settings
        FROM report_configs
        WHERE campaign_settings IS NOT NULL
        LIMIT 1
    """)
    example = cursor.fetchone()
    if example:
        print(f"\n   📝 Пример новой структуры (Report {example[0]} - {example[1]}):")
        settings = json.loads(example[2])
        for cid, s in list(settings.items())[:2]:
            print(f"      Campaign {cid}: {s}")

    conn.close()

    print("\n" + "="*80)
    print("✅ МИГРАЦИЯ ЗАВЕРШЕНА")
    print("="*80)
    print("\nСтарые поля (campaign_frequencies, frequency_variance, total_reach_coefficient)")
    print("сохранены для обратной совместимости и будут удалены в будущей версии.")

if __name__ == '__main__':
    try:
        migrate()
    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
