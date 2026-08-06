# 📊 Интеграция SAPE Reports с Google Sheets

## Кастомное меню в Google Таблицах

Эта интеграция позволяет управлять отчетами SAPE прямо из Google Sheets через кастомное меню.

---

## 1️⃣ Создание Google Apps Script

### Шаги установки:

1. Откройте вашу Google Таблицу
2. Перейдите: **Расширения** → **Apps Script**
3. Удалите весь код по умолчанию
4. Вставьте код ниже
5. Сохраните проект (Ctrl+S)
6. Обновите страницу таблицы

---

## 2️⃣ Код Google Apps Script

### Файл: Code.gs

```javascript
/**
 * ========================================
 * SAPE Reports Panel - Google Sheets Integration
 * ========================================
 */

// URL панели SAPE Reports (ИЗМЕНИТЕ НА ВАШ URL!)
const SAPE_PANEL_URL = 'http://69.48.201.233:5007';

/**
 * Создание кастомного меню при открытии таблицы
 */
function onOpen() {
  const ui = SpreadsheetApp.getUi();

  ui.createMenu('📈 SAPE Reports')
    .addItem('📊 Создать новый отчёт', 'createReport')
    .addItem('🔄 Обновить данные в этом листе', 'updateCurrentSheet')
    .addSeparator()
    .addItem('⚙️ Открыть панель управления', 'openControlPanel')
    .addItem('📋 Список всех отчётов', 'openReportsList')
    .addSeparator()
    .addItem('ℹ️ Справка', 'showHelp')
    .addToUi();

  Logger.log('✅ SAPE Reports menu created');
}

/**
 * Создать новый отчёт для текущей таблицы
 */
function createReport() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const sheetUrl = spreadsheet.getUrl();

  // Формируем URL с предзаполненной ссылкой на таблицу
  const url = `${SAPE_PANEL_URL}/reports/add?sheet_url=${encodeURIComponent(sheetUrl)}`;

  // Показываем диалог с инструкцией
  const ui = SpreadsheetApp.getUi();
  const response = ui.alert(
    '📊 Создание отчёта SAPE',
    'Сейчас откроется панель управления SAPE Reports.\n\n' +
    'Ссылка на эту таблицу уже подставлена автоматически.\n\n' +
    'Заполните остальные поля и сохраните отчёт.',
    ui.ButtonSet.OK_CANCEL
  );

  if (response == ui.Button.OK) {
    // Открываем URL в новой вкладке
    const html = `
      <script>
        window.open('${url}', '_blank');
        google.script.host.close();
      </script>
    `;
    const htmlOutput = HtmlService.createHtmlOutput(html)
      .setWidth(1)
      .setHeight(1);
    ui.showModalDialog(htmlOutput, 'Открытие...');
  }
}

/**
 * Обновить данные в текущем листе
 */
function updateCurrentSheet() {
  const ui = SpreadsheetApp.getUi();
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = SpreadsheetApp.getActiveSheet();
  const sheetUrl = spreadsheet.getUrl();
  const sheetName = sheet.getName();

  // Показываем диалог подтверждения
  const response = ui.alert(
    '🔄 Обновление данных',
    `Обновить данные SAPE для листа "${sheetName}"?\n\n` +
    'Это может занять несколько секунд.',
    ui.ButtonSet.YES_NO
  );

  if (response == ui.Button.YES) {
    try {
      // Показываем индикатор загрузки
      ui.alert('⏳ Обновление...', 'Запрос отправлен. Пожалуйста, подождите.', ui.ButtonSet.OK);

      // Отправляем запрос на обновление
      const url = `${SAPE_PANEL_URL}/api/reports/update-by-sheet`;
      const payload = {
        sheet_url: sheetUrl,
        sheet_name: sheetName
      };

      const options = {
        method: 'post',
        contentType: 'application/json',
        payload: JSON.stringify(payload),
        muteHttpExceptions: true
      };

      const response = UrlFetchApp.fetch(url, options);
      const result = JSON.parse(response.getContentText());

      if (result.success) {
        ui.alert('✅ Успешно', result.message, ui.ButtonSet.OK);
      } else {
        ui.alert('❌ Ошибка', result.error || 'Не удалось обновить данные', ui.ButtonSet.OK);
      }

    } catch (error) {
      ui.alert('❌ Ошибка', 'Не удалось подключиться к панели SAPE:\n' + error.message, ui.ButtonSet.OK);
      Logger.log('Error updating sheet: ' + error);
    }
  }
}

/**
 * Открыть панель управления SAPE Reports
 */
function openControlPanel() {
  const ui = SpreadsheetApp.getUi();
  const html = `
    <script>
      window.open('${SAPE_PANEL_URL}', '_blank');
      google.script.host.close();
    </script>
  `;
  const htmlOutput = HtmlService.createHtmlOutput(html)
    .setWidth(1)
    .setHeight(1);
  ui.showModalDialog(htmlOutput, 'Открытие панели...');
}

/**
 * Открыть список всех отчётов
 */
function openReportsList() {
  const ui = SpreadsheetApp.getUi();
  const html = `
    <script>
      window.open('${SAPE_PANEL_URL}/reports', '_blank');
      google.script.host.close();
    </script>
  `;
  const htmlOutput = HtmlService.createHtmlOutput(html)
    .setWidth(1)
    .setHeight(1);
  ui.showModalDialog(htmlOutput, 'Открытие списка...');
}

/**
 * Показать справку
 */
function showHelp() {
  const ui = SpreadsheetApp.getUi();
  ui.alert(
    'ℹ️ Справка - SAPE Reports',
    '📊 Создать новый отчёт\n' +
    '   Создать автоматизированный отчёт для этой таблицы\n\n' +

    '🔄 Обновить данные в этом листе\n' +
    '   Вручную запустить обновление данных SAPE\n\n' +

    '⚙️ Открыть панель управления\n' +
    '   Перейти в панель SAPE Reports\n\n' +

    '📋 Список всех отчётов\n' +
    '   Просмотреть все настроенные отчёты\n\n' +

    '━━━━━━━━━━━━━━━━━━━━━━━━━━\n' +
    'Панель SAPE Reports автоматизирует загрузку\n' +
    'статистики из SAPE в ваши Google Таблицы.\n\n' +

    `URL панели: ${SAPE_PANEL_URL}`,
    ui.ButtonSet.OK
  );
}

/**
 * Установка триггера при первой установке
 */
function setupTriggers() {
  // Удаляем существующие триггеры
  const triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(trigger => ScriptApp.deleteTrigger(trigger));

  // Создаем новый триггер onOpen
  ScriptApp.newTrigger('onOpen')
    .forSpreadsheet(SpreadsheetApp.getActiveSpreadsheet())
    .onOpen()
    .create();

  Logger.log('✅ Triggers set up');
}
```

---

## 3️⃣ API Endpoint для обновления из Google Sheets

Добавьте этот код в ваш `app.py`:

```python
@app.route('/api/reports/update-by-sheet', methods=['POST'])
def update_by_sheet():
    """
    API endpoint для обновления отчёта из Google Sheets
    Принимает: { "sheet_url": "...", "sheet_name": "..." }
    """
    try:
        data = request.get_json()
        sheet_url = data.get('sheet_url')
        sheet_name = data.get('sheet_name')

        if not sheet_url:
            return jsonify({'error': 'Не указан sheet_url'}), 400

        # Нормализация URL
        sheet_url = sheet_url.split('#')[0].split('?')[0]

        # Поиск отчёта по URL таблицы
        report = ReportConfig.query.filter_by(google_sheet_url=sheet_url).first()

        if not report:
            return jsonify({
                'error': f'Отчёт для таблицы не найден.\n\nСоздайте отчёт через меню:\n📈 SAPE Reports → 📊 Создать новый отчёт'
            }), 404

        # Если указан конкретный лист, проверяем совпадение
        if sheet_name and report.worksheet_name and report.worksheet_name != sheet_name:
            return jsonify({
                'error': f'Этот отчёт настроен для листа "{report.worksheet_name}", а не "{sheet_name}"'
            }), 400

        # Запускаем обновление отчёта
        success = run_report(report.id)

        if success:
            return jsonify({
                'success': True,
                'message': f'✅ Отчёт "{report.name}" успешно обновлён!',
                'report_id': report.id,
                'report_name': report.name
            })
        else:
            return jsonify({
                'error': 'Ошибка при обновлении отчёта. Проверьте логи панели.'
            }), 500

    except Exception as e:
        logger.error(f"Error in update_by_sheet API: {e}")
        return jsonify({'error': str(e)}), 500
```

---

## 4️⃣ Инструкция по установке для пользователей

### Для каждой новой Google Таблицы:

1. **Откройте таблицу**
2. **Расширения** → **Apps Script**
3. **Вставьте код** из раздела 2
4. **Измените URL** на строке 9:
   ```javascript
   const SAPE_PANEL_URL = 'http://69.48.201.233:5007';
   ```
5. **Сохраните** (Ctrl+S)
6. **Закройте Apps Script** и **обновите страницу** таблицы
7. **Появится меню** "📈 SAPE Reports" в верхней панели

---

## 5️⃣ Использование

### Создание нового отчёта:
1. **📈 SAPE Reports** → **📊 Создать новый отчёт**
2. Откроется панель с предзаполненной ссылкой на таблицу
3. Выберите аккаунт, кампании, настройте расписание
4. Сохраните

### Ручное обновление данных:
1. **📈 SAPE Reports** → **🔄 Обновить данные в этом листе**
2. Подтвердите обновление
3. Дождитесь завершения

---

## 6️⃣ Преимущества интеграции

✅ **Быстрый доступ** - всё управление прямо из Google Sheets
✅ **Автоматическое заполнение** - URL таблицы подставляется автоматически
✅ **Ручное обновление** - можно обновить данные в любой момент
✅ **Удобная навигация** - быстрый переход в панель управления
✅ **Не требует расширений** - работает через встроенный Apps Script

---

## 7️⃣ Безопасность

⚠️ **Важно:**
- Apps Script код виден только владельцу таблицы
- API endpoint требует корректный URL таблицы
- Отчёты обновляются только если настроены в панели
- Нет доступа к учётным данным SAPE из Apps Script

---

## 8️⃣ Траблшутинг

### Меню не появляется
- Обновите страницу (F5)
- Проверьте, что код сохранён в Apps Script
- Выполните `setupTriggers()` вручную из Apps Script

### Ошибка "Не удалось подключиться к панели SAPE"
- Проверьте URL панели в переменной `SAPE_PANEL_URL`
- Убедитесь, что панель запущена: `systemctl status sape-reports`
- Проверьте доступность: `curl http://69.48.201.233:5007`

### Отчёт не найден
- Создайте отчёт через **📈 SAPE Reports → 📊 Создать новый отчёт**
- Проверьте, что URL таблицы совпадает в панели управления

---

**Готово!** Теперь можно управлять SAPE Reports прямо из Google Sheets 🎉
