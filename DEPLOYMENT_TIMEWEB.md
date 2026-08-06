# Развертывание SAPE Reports Panel на Timeweb Cloud

## Информация о сервере

**Провайдер:** Timeweb Cloud
**IP адрес:** 85.239.51.28
**Операционная система:** Ubuntu 22.04 LTS
**Конфигурация:** 2 vCPU, 2 GB RAM, 30 GB SSD
**Стоимость:** 550 ₽/месяц

### Доступ к серверу

**SSH подключение:**
```bash
ssh -i ~/.ssh/ionos_sape_reports root@85.239.51.28
```

**Root пароль:** xvQAK^2Lq9u+Ne

**SSH ключ:**
- Приватный ключ: `~/.ssh/ionos_sape_reports`
- Публичный ключ: `~/.ssh/ionos_sape_reports.pub`

## Доступ к приложению

**Веб-интерфейс:** http://85.239.51.28:5007/

## Структура на сервере

```
/root/web-projects/sape-reports/
├── main.py                    # Основной файл приложения (переименован из app.py)
├── wsgi.py                    # WSGI entry point для Gunicorn
├── requirements.txt           # Зависимости Python
├── credentials.json           # Google Service Account credentials
├── google_credentials.json    # Симлинк на credentials.json
├── app/                       # Пакет приложения
│   ├── __init__.py
│   ├── models.py
│   ├── routes.py
│   ├── scheduler.py
│   ├── google_sheets_client.py
│   ├── sape_client.py
│   └── templates/
├── database/
│   └── sape_reports.db       # База данных SQLite
└── venv/                      # Виртуальное окружение Python
```

## Системный сервис

**Файл конфигурации:** `/etc/systemd/system/sape-reports.service`

### Управление сервисом

```bash
# Проверить статус
systemctl status sape-reports.service

# Перезапустить сервис
systemctl restart sape-reports.service

# Остановить сервис
systemctl stop sape-reports.service

# Запустить сервис
systemctl start sape-reports.service

# Посмотреть логи
journalctl -u sape-reports.service -f

# Посмотреть последние 100 строк логов
journalctl -u sape-reports.service -n 100 --no-pager
```

### Конфигурация сервиса

```ini
[Unit]
Description=SAPE Reports Panel - Automated Statistics
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/web-projects/sape-reports
Environment="PATH=/root/web-projects/sape-reports/venv/bin"
ExecStart=/root/web-projects/sape-reports/venv/bin/gunicorn -w 4 -b 0.0.0.0:5007 --timeout 120 main:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Параметры Gunicorn:**
- **4 воркера** (-w 4)
- **Порт:** 5007
- **Timeout:** 120 секунд
- **Автоперезапуск** при сбоях

## Google Sheets API

**Service Account Email:**
```
sape-reports-bot@orbital-outpost-484308-s3.iam.gserviceaccount.com
```

**Важно:** При создании новых Google таблиц для отчетов нужно дать доступ (Editor) этому email адресу.

## Решенные проблемы при развертывании

### 1. Конфликт имен app.py и app/

**Проблема:**
```
ImportError: cannot import name 'app' from 'app'
```

**Решение:** Переименовал `app.py` → `main.py` на сервере

### 2. Путь к Google credentials

**Проблема:**
```
[Errno 2] No such file or directory: '/root/web-projects/sape-reports/google_credentials.json'
```

**Причина:** Код ожидает файл `google_credentials.json`, но файл был загружен как `credentials.json`

**Решение:** Создан симлинк
```bash
cd /root/web-projects/sape-reports
ln -s credentials.json google_credentials.json
```

### 3. Кэширование воркеров Gunicorn

**Проблема:** После создания симлинка ошибка продолжала появляться в логах

**Решение:** Жесткий перезапуск сервиса (stop → start вместо restart)

## Обновление кода на сервере

Для обновления кода на сервере:

```bash
# На локальной машине
cd "/Users/annabereznyak/Desktop/Все проекты/api_google sheets"

# Синхронизировать файлы (исключая venv, database, __pycache__)
rsync -avz --exclude 'venv' \
           --exclude 'database' \
           --exclude '__pycache__' \
           --exclude '*.pyc' \
           --exclude '.git' \
           --exclude 'google_credentials.json' \
           -e "ssh -i ~/.ssh/ionos_sape_reports" \
           ./ root@85.239.51.28:/root/web-projects/sape-reports/

# На сервере - перезапустить сервис
ssh -i ~/.ssh/ionos_sape_reports root@85.239.51.28 "systemctl restart sape-reports.service"
```

## Резервное копирование базы данных

### Скачать базу данных с сервера

```bash
scp -i ~/.ssh/ionos_sape_reports \
    root@85.239.51.28:/root/web-projects/sape-reports/database/sape_reports.db \
    ./database/sape_reports.db.backup
```

### Загрузить базу данных на сервер

```bash
scp -i ~/.ssh/ionos_sape_reports \
    ./database/sape_reports.db \
    root@85.239.51.28:/root/web-projects/sape-reports/database/sape_reports.db
```

## Мониторинг

### Проверка работоспособности

```bash
# Проверить HTTP статус
curl -s -o /dev/null -w "HTTP Status: %{http_code}\n" http://85.239.51.28:5007/

# Проверить статус сервиса
ssh -i ~/.ssh/ionos_sape_reports root@85.239.51.28 "systemctl is-active sape-reports.service"

# Проверить использование ресурсов
ssh -i ~/.ssh/ionos_sape_reports root@85.239.51.28 "systemctl status sape-reports.service --no-pager | grep -E 'Memory|CPU|Active'"
```

### Типичное потребление ресурсов

- **Память:** ~220-230 MB
- **CPU:** 3-4 секунды (cumulative)
- **Процессы:** 1 master + 4 workers = 5 процессов

## Проверка работы отчетов

После успешного развертывания:

1. Открыть http://85.239.51.28:5007/
2. Выбрать отчет #7 "Стройдвор по гео"
3. Нажать "Обновить отчет"
4. Проверить логи:
   ```bash
   ssh -i ~/.ssh/ionos_sape_reports root@85.239.51.28 "journalctl -u sape-reports.service -f"
   ```

5. Должны увидеть в логах:
   ```
   📊 TOTAL REPORT MODE: Processing 5 campaigns
   ✅ Campaign 282610 (Екатеринбург_1379к_48к):
      Shows: XXX,XXX, Clicks: XXX
   ...
   ✅ Total report complete: 5/5 campaigns updated
   ```

## Автоматические задачи (APScheduler)

Приложение использует APScheduler для автоматического обновления отчетов по расписанию.

Проверить запланированные задачи можно в веб-интерфейсе:
- Страница списка отчетов показывает время следующего обновления

## Безопасность

**Важные замечания:**

1. **Firewall:** Порт 5007 открыт для всех IP адресов
2. **HTTPS:** В текущей конфигурации используется HTTP (не HTTPS)
3. **Аутентификация:** Нет встроенной аутентификации в приложении
4. **SSH ключи:** Приватный ключ хранится локально в `~/.ssh/ionos_sape_reports`

**Рекомендации для production:**

- Настроить firewall для ограничения доступа к порту 5007
- Добавить reverse proxy (Nginx) с SSL/TLS сертификатом
- Добавить базовую аутентификацию (Flask-Login или Basic Auth в Nginx)

## Дата развертывания

**26 апреля 2026**

Сервис успешно развернут и работает стабильно.
