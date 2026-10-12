# 🚀 Деплой обновления мониторинга (VTR/CTR улучшения)

**Дата:** 12 октября 2026
**Версия:** Monitoring VTR/CTR Update

---

## 📋 Что нового в этом обновлении

### 1. База данных
- ✅ Добавлена колонка `fact_vtr` для хранения фактических VTR/VR данных
- ✅ VTR для видео форматов (V, CTV)
- ✅ VR для баннерных форматов (B, TGB)

### 2. Планировщик задач
- ✅ Автообновление мониторинга изменено с **09:00** на **03:00** МСК
- ✅ Добавлены задержки между запросами для предотвращения таймаутов:
  - 2 секунды между обновлениями мониторинга
  - 3 секунды между синхронизацией аккаунтов
  - 2 секунды между обновлениями отчетов

### 3. UI/UX улучшения
- ✅ Строка "Выполнение" теперь показывает разницу вместо процентов:
  - **CTR:** КПИ 2.00%, факт 2.06% → показывает **+0.06** (зеленый)
  - **VTR:** КПИ 80%, факт 91% → показывает **+11** (зеленый)
  - Отрицательные значения красным цветом
- ✅ VTR теперь сохраняется и отображается как целое число (80%, не 80.00%)

### 4. Новая функциональность
- ✅ Добавлена загрузка Adriver Excel файлов для IVT данных
- ✅ Кнопка "Adriver .xlsx" в меню карточек мониторинга
- ✅ Автоматический парсинг IVT/GIVT/SIVT из Excel

### 5. API улучшения
- ✅ SAPE API теперь загружает VTR и VR метрики
- ✅ Автоматическое определение формата (видео/баннер)
- ✅ Округление VTR/VR до целых чисел

---

## 🔧 Измененные файлы

### Основные файлы:
1. **app.py**
   - Изменено время планировщика (09:00 → 03:00)
   - Добавлены задержки в `scheduled_refresh_all_monitorings()`
   - Добавлены задержки в `scheduled_sync_all_accounts()`
   - Добавлены задержки в `scheduled_update_reports()`
   - Добавлен endpoint `/upload_adriver_excel/<monitoring_id>`
   - Изменено сохранение VTR как целое число
   - Добавлена загрузка VTR/VR из SAPE API

2. **app/models.py**
   - Добавлено поле `fact_vtr`
   - Исправлены методы `get_plan_vr()` и `get_fact_vr()` (возвращают сохраненные значения)
   - Добавлен метод `get_ctr_diff()` для разницы CTR
   - Добавлен метод `get_vtr_diff()` для разницы VTR
   - Обновлен `is_video_format()` для поддержки CTV

3. **app/templates/monitoring.html**
   - Изменен input для VTR (step="1" для целых чисел)
   - Убрано hardcoded value="70" из формы
   - Изменено отображение CTR/VTR в строке "Выполнение" на разницу
   - Добавлена кнопка "Adriver .xlsx" в kebab меню
   - Добавлено модальное окно загрузки Excel
   - Изменен формат отображения VTR: %.0f%% вместо %.2f%%

4. **app/api/sape_client.py**
   - Добавлены поля "vtr" и "vr" в запрос к API
   - Увеличен таймаут до 30 секунд

### Новые файлы:
- `parse_adriver_excel.py` - парсер Excel файлов Adriver
- `migrations/add_fact_vtr_column.sql` - SQL миграция
- `deploy_monitoring_vtr_update.sh` - скрипт деплоя

### Вспомогательные файлы:
- `update_monitoring_from_excel.py` - скрипт обновления мониторинга из Excel
- `ADRIVER_API_README.md` - документация по Adriver API

---

## 🚀 Инструкция по деплою

### Вариант 1: Автоматический деплой (рекомендуется)

**На локальной машине:**

```bash
cd "/Users/annabereznyak/Desktop/Все проекты/api_google sheets"

# 1. Добавить изменения в Git
git add app.py app/models.py app/templates/monitoring.html app/api/sape_client.py
git add migrations/add_fact_vtr_column.sql
git add deploy_monitoring_vtr_update.sh
git add parse_adriver_excel.py

# 2. Создать коммит
git commit -m "Monitoring improvements: VTR/CTR updates, Adriver Excel upload, scheduler optimization

- Add fact_vtr column for storing actual VTR/VR data
- Change auto-update time from 09:00 to 03:00 MSK
- Add delays between API requests to prevent timeouts
- Change CTR/VTR display in performance row to show difference
- Add Adriver Excel upload functionality for IVT data
- Fix VTR saving and display as integer values
- Update SAPE API client to load VTR/VR metrics"

# 3. Запушить в GitHub
git push origin main

# 4. Сделать скрипт исполняемым
chmod +x deploy_monitoring_vtr_update.sh

# 5. Запустить деплой
./deploy_monitoring_vtr_update.sh
```

Скрипт автоматически:
- Подтянет код на сервере
- Выполнит миграцию БД
- Перезапустит сервис
- Проверит что все работает

---

### Вариант 2: Ручной деплой

**1. Закоммитить и запушить код:**
```bash
cd "/Users/annabereznyak/Desktop/Все проекты/api_google sheets"
git add -A
git commit -m "Monitoring VTR/CTR improvements"
git push origin main
```

**2. На сервере подтянуть код:**
```bash
ssh root@74.208.242.125
cd /root/web-projects/sape-reports
git pull origin main
```

**3. Выполнить миграцию БД:**
```bash
cd /root/web-projects/sape-reports
sqlite3 database/sape_reports.db "ALTER TABLE monitoring_campaigns ADD COLUMN fact_vtr FLOAT;" 2>/dev/null || echo "Column already exists"

# Проверить что колонка добавлена
sqlite3 database/sape_reports.db "SELECT name, type FROM pragma_table_info('monitoring_campaigns') WHERE name = 'fact_vtr';"
```

**4. Перезапустить сервис:**
```bash
systemctl restart sape-reports
systemctl status sape-reports
```

**5. Проверить логи:**
```bash
journalctl -u sape-reports -f
```

---

## ✅ Проверка после деплоя

### 1. Проверить что сервис запущен
```bash
ssh root@74.208.242.125
systemctl status sape-reports
```

Должно быть: `Active: active (running)`

### 2. Проверить планировщик
```bash
journalctl -u sape-reports | grep "Scheduler started"
```

Должна быть строка:
```
✅ Scheduler started:
   - Daily monitoring refresh at 03:00 Moscow time (every day)
```

### 3. Проверить в браузере
1. Открыть: http://74.208.242.125:5500/monitoring
2. Проверить что VTR отображается корректно (целые числа, например 80%)
3. Открыть карточку мониторинга для редактирования
4. Проверить что VTR сохраняется правильно
5. Проверить строку "Выполнение" - должна показывать разницу (например +11 или -5)
6. Проверить кнопку "Adriver .xlsx" в меню карточки

### 4. Проверить новую функциональность
1. Нажать на три точки в карточке мониторинга
2. Выбрать "Adriver .xlsx"
3. Загрузить Excel файл с IVT данными
4. Проверить что IVT метрики обновились

### 5. Проверить автообновление (опционально)
Дождаться 03:00 МСК на следующий день и проверить логи:
```bash
journalctl -u sape-reports --since "03:00" --until "04:00" | grep "SCHEDULED MONITORING REFRESH"
```

---

## 🔍 Что проверять

- [ ] Сервис запущен и работает
- [ ] База данных содержит колонку fact_vtr
- [ ] Планировщик показывает время 03:00 в логах
- [ ] VTR отображается как целое число (80%, не 80.00%)
- [ ] VTR сохраняется из формы редактирования
- [ ] Строка "Выполнение" показывает разницу для CTR/VTR
- [ ] Кнопка "Adriver .xlsx" доступна в меню
- [ ] Загрузка Excel работает корректно
- [ ] SAPE API загружает VTR/VR метрики

---

## 🛠️ Откат изменений (если что-то пошло не так)

```bash
# На сервере
ssh root@74.208.242.125
cd /root/web-projects/sape-reports

# Откатить код на предыдущую версию
git log --oneline -5  # Посмотреть последние коммиты
git checkout <previous-commit-hash>

# Перезапустить сервис
systemctl restart sape-reports

# Проверить статус
systemctl status sape-reports
```

---

## 📊 Технические детали

### Миграция БД
```sql
ALTER TABLE monitoring_campaigns ADD COLUMN fact_vtr FLOAT;
```

### Новые методы в models.py
```python
def get_ctr_diff(self):
    """CTR: показать разницу (+0.06 или -0.06)"""

def get_vtr_diff(self):
    """VTR: показать разницу (+11 или -9)"""
```

### Изменения в планировщике
```python
# Было: hour=9
trigger=CronTrigger(hour=3, minute=0)  # Изменено на 03:00

# Добавлены задержки
time.sleep(2)  # между мониторингами
time.sleep(3)  # между аккаунтами
```

---

## 📞 Поддержка

При возникновении проблем:

1. **Проверить логи:**
   ```bash
   journalctl -u sape-reports -n 100
   ```

2. **Проверить базу данных:**
   ```bash
   sqlite3 database/sape_reports.db "PRAGMA table_info(monitoring_campaigns);"
   ```

3. **Перезапустить сервис:**
   ```bash
   systemctl restart sape-reports
   ```

---

**Готово к деплою!** 🚀
