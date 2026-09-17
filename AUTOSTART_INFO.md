# Настройка автозапуска сервера при загрузке системы

## ✅ Текущий статус

Сервер настроен для автоматического запуска при загрузке macOS через LaunchAgent.

- **URL сервера:** http://127.0.0.1:5006/reports
- **LaunchAgent:** `~/Library/LaunchAgents/com.local.api-google-sheets.plist`
- **Рабочая директория:** `/Users/annabereznyak/Desktop/Все проекты/api_google sheets`

## 📋 Управление автозапуском

### Проверить статус сервера
```bash
launchctl list | grep api-google-sheets
lsof -Pi :5006 -sTCP:LISTEN
```

### Остановить автозапуск
```bash
launchctl unload ~/Library/LaunchAgents/com.local.api-google-sheets.plist
```

### Включить автозапуск
```bash
launchctl load ~/Library/LaunchAgents/com.local.api-google-sheets.plist
```

### Перезапустить сервис
```bash
launchctl unload ~/Library/LaunchAgents/com.local.api-google-sheets.plist
launchctl load ~/Library/LaunchAgents/com.local.api-google-sheets.plist
```

### Удалить автозапуск полностью
```bash
launchctl unload ~/Library/LaunchAgents/com.local.api-google-sheets.plist
rm ~/Library/LaunchAgents/com.local.api-google-sheets.plist
```

## 📝 Логи

- **Стандартный вывод:** `server_local.log`
- **Ошибки:** `server_local_error.log`

### Просмотр логов в реальном времени
```bash
cd "/Users/annabereznyak/Desktop/Все проекты/api_google sheets"
tail -f server_local.log
```

## 🔧 Ручной запуск/остановка

Если нужно управлять сервером вручную (без автозагрузки):

### Запуск
```bash
cd "/Users/annabereznyak/Desktop/Все проекты/api_google sheets"
./start_local.sh
```

### Остановка
```bash
cd "/Users/annabereznyak/Desktop/Все проекты/api_google sheets"
./stop_local.sh
```

### Проверка статуса
```bash
cd "/Users/annabereznyak/Desktop/Все проекты/api_google sheets"
./status_local.sh
```

## ⚙️ Конфигурация LaunchAgent

Файл `com.local.api-google-sheets.plist` содержит:
- **RunAtLoad:** true - запуск при загрузке системы
- **KeepAlive:** true - автоматический перезапуск при сбое
- **WorkingDirectory:** путь к проекту
- **StandardOutPath/StandardErrorPath:** пути к логам

## 🚀 Проверка работы

После перезагрузки компьютера сервер должен автоматически запуститься.
Проверить можно открыв в браузере: http://127.0.0.1:5006/reports

Или через терминал:
```bash
curl http://127.0.0.1:5006/
```

Должен вернуть код 302 (редирект) или 200 (успех).

## ❓ Решение проблем

### Сервер не запускается автоматически
1. Проверьте логи ошибок:
   ```bash
   cat "/Users/annabereznyak/Desktop/Все проекты/api_google sheets/server_local_error.log"
   ```

2. Проверьте статус LaunchAgent:
   ```bash
   launchctl list | grep api-google-sheets
   ```

3. Проверьте, установлены ли зависимости:
   ```bash
   cd "/Users/annabereznyak/Desktop/Все проекты/api_google sheets"
   source venv/bin/activate
   pip install -r requirements.txt
   ```

### Порт уже занят
Если порт 5006 занят другим процессом:
```bash
lsof -ti :5006 | xargs kill -9
```

### База данных не создается
Убедитесь, что файл базы данных существует:
```bash
cd "/Users/annabereznyak/Desktop/Все проекты/api_google sheets"
ls -la *.db
```

Если базы нет, создайте её:
```bash
cd "/Users/annabereznyak/Desktop/Все проекты/api_google sheets"
source venv/bin/activate
python3 -c "from app import app, db; app.app_context().push(); db.create_all()"
```
