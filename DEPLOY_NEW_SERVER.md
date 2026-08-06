# Развёртывание на новом сервере

## Шаг 1: Подготовка сервера

### 1.1. Заказать VPS
- Ubuntu 22.04 или новее
- Минимум 2GB RAM, 2 CPU
- Публичный IP-адрес
- Доступ по SSH

### 1.2. Подключиться к серверу
```bash
ssh root@<НОВЫЙ_IP>
```

### 1.3. Обновить систему
```bash
apt update && apt upgrade -y
```

### 1.4. Установить необходимые пакеты
```bash
apt install -y python3 python3-pip python3-venv nginx git
```

## Шаг 2: Клонировать репозиторий

```bash
cd /root
mkdir -p web-projects
cd web-projects
git clone <URL_ВАШЕГО_GITHUB_РЕПОЗИТОРИЯ> sape-reports
cd sape-reports
```

## Шаг 3: Настроить Python окружение

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Шаг 4: Загрузить критические файлы с локальной машины

### 4.1. Google Sheets credentials
На **локальной машине** выполните:
```bash
scp "/Users/annabereznyak/Desktop/Все проекты/api_google sheets/google-sheets-service-account.json" root@<НОВЫЙ_IP>:/root/web-projects/sape-reports/
```

### 4.2. База данных (апрельская версия)
На **локальной машине** выполните:
```bash
scp -r "/Users/annabereznyak/Desktop/Все проекты/api_google sheets/database" root@<НОВЫЙ_IP>:/root/web-projects/sape-reports/
```

### 4.3. Проверить загрузку
На **сервере**:
```bash
ls -la /root/web-projects/sape-reports/
# Должны быть:
# - google-sheets-service-account.json
# - database/sape_reports.db
```

## Шаг 5: Настроить systemd сервис

### 5.1. Создать файл сервиса
```bash
nano /etc/systemd/system/sape-reports.service
```

### 5.2. Содержимое файла:
```ini
[Unit]
Description=SAPE Reports Panel
After=network.target

[Service]
Type=notify
User=root
WorkingDirectory=/root/web-projects/sape-reports
Environment="PATH=/root/web-projects/sape-reports/venv/bin"
ExecStart=/root/web-projects/sape-reports/venv/bin/gunicorn \
    --workers 4 \
    --bind 0.0.0.0:5007 \
    --timeout 120 \
    --access-logfile /var/log/sape-reports-access.log \
    --error-logfile /var/log/sape-reports-error.log \
    wsgi:application
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 5.3. Активировать сервис
```bash
systemctl daemon-reload
systemctl enable sape-reports
systemctl start sape-reports
systemctl status sape-reports
```

## Шаг 6: Настроить Nginx (опционально)

Если хотите использовать Nginx как reverse proxy:

```bash
nano /etc/nginx/sites-available/sape-reports
```

Содержимое:
```nginx
server {
    listen 80;
    server_name <НОВЫЙ_IP>;

    location / {
        proxy_pass http://127.0.0.1:5007;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 120s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }
}
```

Активировать:
```bash
ln -s /etc/nginx/sites-available/sape-reports /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx
```

## Шаг 7: Проверка работы

### 7.1. Прямой доступ к приложению
```
http://<НОВЫЙ_IP>:5007/login
```

### 7.2. Через Nginx (если настроили)
```
http://<НОВЫЙ_IP>/login
```

### 7.3. Проверить логи
```bash
tail -f /var/log/sape-reports-error.log
tail -f /root/web-projects/sape-reports/app_logs.log
```

## Шаг 8: Восстановить данные отчётов

Поскольку база данных с апреля 2026, нужно:

1. **Войти в систему** под существующим пользователем
2. **Проверить отчёты** - какие работают, какие нужно пересоздать
3. **Синхронизировать кампании** для каждого аккаунта:
   ```bash
   cd /root/web-projects/sape-reports
   source venv/bin/activate
   python sync_lazurny.py  # Для аккаунта "Лазурный берег"
   # Повторить для других аккаунтов
   ```
4. **Обновить форматы кампаний** (если нужно):
   ```bash
   python3 << 'EOF'
   import sqlite3
   conn = sqlite3.connect('/root/web-projects/sape-reports/database/sape_reports.db')
   cursor = conn.cursor()
   # Проверить OLV кампании
   cursor.execute("SELECT campaign_id, format_type FROM campaigns WHERE campaign_id IN ('291004', '291003')")
   print(cursor.fetchall())
   # Если формат неверный, исправить:
   # cursor.execute("UPDATE campaigns SET format_type='V' WHERE campaign_id IN ('291004', '291003')")
   # conn.commit()
   conn.close()
   EOF
   ```

## Шаг 9: Настроить SSH ключ (опционально)

Если хотите использовать существующий SSH ключ `ionos_sape_reports`:

```bash
# На локальной машине
ssh-copy-id -i ~/.ssh/ionos_sape_reports.pub root@<НОВЫЙ_IP>
```

Тогда сможете подключаться:
```bash
ssh -i ~/.ssh/ionos_sape_reports root@<НОВЫЙ_IP>
```

## Шаг 10: Обновление кода в будущем

После создания GitHub репозитория:

```bash
cd /root/web-projects/sape-reports
git pull origin main
systemctl restart sape-reports
```

## Полезные команды

### Перезапуск сервиса
```bash
systemctl restart sape-reports
```

### Остановка сервиса
```bash
systemctl stop sape-reports
```

### Просмотр логов в реальном времени
```bash
journalctl -u sape-reports -f
```

### Проверка статуса
```bash
systemctl status sape-reports
```

### Проверка портов
```bash
netstat -tulpn | grep 5007
```

## Важно!

1. База данных содержит только данные до апреля 2026
2. Все отчёты, созданные с апреля по июль, придётся пересоздать вручную
3. Credentials для Google Sheets и SAPE API уже есть в базе данных
4. После развёртывания обязательно протестировать все отчёты
5. Включить автоматическое обновление через веб-интерфейс

## Что уже работает в коде

- Автоматическое определение колонок в сводных отчётах
- Поддержка нескольких кампаний в одной ячейке
- Неограниченный поиск заголовков
- Правильная группировка данных по таблицам
- Функционал сброса пароля для @sape.ru
