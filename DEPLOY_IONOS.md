# 🚀 Развертывание SAPE Reports Panel на IONOS VPS

## 📋 Предварительные требования

- Доступ к серверу IONOS VPS (69.48.201.233)
- Python 3.8+
- Git
- Права sudo/root

---

## 1️⃣ Подготовка сервера

### Подключение к серверу
```bash
ssh root@69.48.201.233
```

### Установка необходимых пакетов (если еще не установлены)
```bash
apt update
apt install -y python3 python3-pip python3-venv git
```

---

## 2️⃣ Создание GitHub репозитория

### На локальной машине

1. **Инициализация git (если еще не сделано)**
```bash
cd "/Users/annabereznyak/Desktop/Все проекты/api_google sheets"
git init
```

2. **Создание .gitignore**
```bash
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
ENV/
env/

# Database
database/*.db
database/*.db-journal

# Logs
*.log
logs/

# Credentials
credentials.json
service_account.json
*.json
!package.json

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Flask
instance/
.webassets-cache

# Backups
backups/
*.backup
*.bak
EOF
```

3. **Создание requirements.txt**
```bash
cat > requirements.txt << 'EOF'
Flask==3.0.0
Flask-SQLAlchemy==3.1.1
gspread==6.1.4
google-auth==2.35.0
google-auth-oauthlib==1.2.1
google-auth-httplib2==0.2.0
requests==2.32.3
APScheduler==3.10.4
gunicorn==21.2.0
python-dotenv==1.0.0
EOF
```

4. **Первый коммит**
```bash
git add .
git commit -m "Initial commit: SAPE Reports Panel with Total Report feature"
```

5. **Создание репозитория на GitHub**
- Перейти на https://github.com/new
- Название: `sape-reports-panel`
- Приватный репозиторий
- Создать

6. **Push на GitHub**
```bash
git remote add origin git@github.com:ВАШ_USERNAME/sape-reports-panel.git
git branch -M main
git push -u origin main
```

---

## 3️⃣ Развертывание на сервере

### На сервере IONOS

1. **Создание директории проекта**
```bash
mkdir -p /root/web-projects
cd /root/web-projects
```

2. **Клонирование репозитория**
```bash
git clone git@github.com:ВАШ_USERNAME/sape-reports-panel.git sape-reports
cd sape-reports
```

3. **Создание виртуального окружения**
```bash
python3 -m venv venv
source venv/bin/activate
```

4. **Установка зависимостей**
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

5. **Создание необходимых директорий**
```bash
mkdir -p database
mkdir -p logs
mkdir -p backups
```

6. **Загрузка credentials.json**
```bash
# На локальной машине
scp "/Users/annabereznyak/Desktop/Все проекты/api_google sheets/credentials.json" root@69.48.201.233:/root/web-projects/sape-reports/
```

7. **Инициализация базы данных**
```bash
source venv/bin/activate
python3 -c "from app import db, app; app.app_context().push(); db.create_all(); print('✅ База данных создана')"
```

---

## 4️⃣ Создание Systemd сервиса

### Создание файла сервиса
```bash
cat > /etc/systemd/system/sape-reports.service << 'EOF'
[Unit]
Description=SAPE Reports Panel - Automated Statistics
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/web-projects/sape-reports
Environment="PATH=/root/web-projects/sape-reports/venv/bin"
ExecStart=/root/web-projects/sape-reports/venv/bin/gunicorn -w 4 -b 0.0.0.0:5007 --timeout 120 wsgi:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

### Создание wsgi.py (если еще не существует)
```bash
cat > /root/web-projects/sape-reports/wsgi.py << 'EOF'
from app import app

if __name__ == "__main__":
    app.run()
EOF
```

### Активация и запуск сервиса
```bash
# Перезагрузка конфигурации systemd
systemctl daemon-reload

# Включение автозапуска
systemctl enable sape-reports.service

# Запуск сервиса
systemctl start sape-reports.service

# Проверка статуса
systemctl status sape-reports.service
```

---

## 5️⃣ Настройка файрвола

### Открытие порта 5007
```bash
# Если используется UFW
ufw allow 5007/tcp
ufw reload

# Если используется iptables
iptables -A INPUT -p tcp --dport 5007 -j ACCEPT
iptables-save > /etc/iptables/rules.v4
```

---

## 6️⃣ Проверка работоспособности

### Проверка доступности
```bash
# На сервере
curl http://localhost:5007

# С локальной машины
curl http://69.48.201.233:5007
```

### Открытие в браузере
```
http://69.48.201.233:5007
```

---

## 7️⃣ Управление сервисом

### Основные команды
```bash
# Просмотр статуса
systemctl status sape-reports.service

# Просмотр логов
journalctl -u sape-reports.service -f

# Просмотр последних 100 строк логов
journalctl -u sape-reports.service -n 100

# Перезапуск сервиса
systemctl restart sape-reports.service

# Остановка сервиса
systemctl stop sape-reports.service

# Запуск сервиса
systemctl start sape-reports.service
```

### Просмотр логов приложения
```bash
# Логи Flask приложения
tail -f /root/web-projects/sape-reports/logs/sape_reports.log

# Логи scheduler
tail -f /tmp/sape_reports.log
```

---

## 8️⃣ Обновление приложения

### При изменениях в коде

1. **На локальной машине - commit и push**
```bash
cd "/Users/annabereznyak/Desktop/Все проекты/api_google sheets"
git add .
git commit -m "Описание изменений"
git push origin main
```

2. **На сервере - pull и restart**
```bash
cd /root/web-projects/sape-reports
git pull origin main
systemctl restart sape-reports.service
systemctl status sape-reports.service
```

### При изменении зависимостей
```bash
cd /root/web-projects/sape-reports
source venv/bin/activate
pip install -r requirements.txt
systemctl restart sape-reports.service
```

---

## 9️⃣ Резервное копирование

### Создание бекапа базы данных
```bash
# Ручной бекап
cd /root/web-projects/sape-reports
cp database/sape_reports.db backups/sape_reports_$(date +%Y%m%d_%H%M%S).db

# Скачать бекап на локальную машину
scp root@69.48.201.233:/root/web-projects/sape-reports/backups/sape_reports_*.db "/Users/annabereznyak/Desktop/Все проекты/api_google sheets/backups/"
```

### Автоматический бекап (cron)
```bash
# Создать скрипт бекапа
cat > /root/web-projects/sape-reports/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/root/web-projects/sape-reports/backups"
DB_PATH="/root/web-projects/sape-reports/database/sape_reports.db"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR
cp $DB_PATH $BACKUP_DIR/sape_reports_$DATE.db

# Удалить бекапы старше 30 дней
find $BACKUP_DIR -name "sape_reports_*.db" -mtime +30 -delete

echo "✅ Backup created: sape_reports_$DATE.db"
EOF

chmod +x /root/web-projects/sape-reports/backup.sh

# Добавить в crontab (каждый день в 3:00)
(crontab -l 2>/dev/null; echo "0 3 * * * /root/web-projects/sape-reports/backup.sh") | crontab -
```

---

## 🔟 Траблшутинг

### Сервис не запускается
```bash
# Просмотр детальных логов
journalctl -u sape-reports.service -n 200 --no-pager

# Проверка синтаксиса Python
cd /root/web-projects/sape-reports
source venv/bin/activate
python3 -c "import app; print('✅ Синтаксис корректен')"

# Ручной запуск для диагностики
cd /root/web-projects/sape-reports
source venv/bin/activate
python3 app.py
```

### Ошибка импорта модулей
```bash
# Переустановка зависимостей
cd /root/web-projects/sape-reports
source venv/bin/activate
pip install --force-reinstall -r requirements.txt
```

### Проблемы с Google Sheets API
```bash
# Проверка наличия credentials.json
ls -lh /root/web-projects/sape-reports/credentials.json

# Проверка прав доступа
chmod 600 /root/web-projects/sape-reports/credentials.json
```

### Порт занят
```bash
# Проверить что использует порт 5007
lsof -i :5007
netstat -tulpn | grep 5007

# Убить процесс (если нужно)
kill -9 <PID>
```

### База данных заблокирована
```bash
# Проверить процессы
ps aux | grep sape-reports

# Удалить lock файлы
cd /root/web-projects/sape-reports/database
rm -f sape_reports.db-journal
```

---

## 1️⃣1️⃣ Мониторинг

### Проверка работоспособности
```bash
# Создать healthcheck скрипт
cat > /root/web-projects/sape-reports/healthcheck.sh << 'EOF'
#!/bin/bash
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5007)

if [ $RESPONSE -eq 200 ]; then
    echo "✅ SAPE Reports Panel is running (HTTP $RESPONSE)"
    exit 0
else
    echo "❌ SAPE Reports Panel is down (HTTP $RESPONSE)"
    systemctl restart sape-reports.service
    exit 1
fi
EOF

chmod +x /root/web-projects/sape-reports/healthcheck.sh

# Добавить в crontab (каждые 5 минут)
(crontab -l 2>/dev/null; echo "*/5 * * * * /root/web-projects/sape-reports/healthcheck.sh >> /root/web-projects/sape-reports/logs/healthcheck.log 2>&1") | crontab -
```

---

## 1️⃣2️⃣ Информация о сервисе

- **URL**: http://69.48.201.233:5007
- **Порт**: 5007
- **Путь на сервере**: /root/web-projects/sape-reports
- **Systemd сервис**: sape-reports.service
- **Логи**: /root/web-projects/sape-reports/logs/
- **База данных**: /root/web-projects/sape-reports/database/sape_reports.db
- **Бекапы**: /root/web-projects/sape-reports/backups/

---

## ✅ Чеклист развертывания

- [ ] Создан GitHub репозиторий
- [ ] Код залит на GitHub
- [ ] Проект клонирован на сервер
- [ ] Виртуальное окружение создано
- [ ] Зависимости установлены
- [ ] credentials.json загружен на сервер
- [ ] База данных инициализирована
- [ ] Systemd сервис создан и активирован
- [ ] Порт 5007 открыт в файрволе
- [ ] Сервис запущен и доступен
- [ ] Настроено автоматическое резервное копирование
- [ ] Настроен healthcheck мониторинг

---

## 🎯 Следующие шаги

1. **Интеграция с Google Sheets** - создать Google Apps Script для кастомного меню
2. **API endpoint** - добавить `/api/reports/update-by-sheet` для обновления из таблиц
3. **SSL сертификат** - настроить HTTPS через Let's Encrypt (опционально)
4. **Nginx reverse proxy** - для красивых URL (опционально)

---

**Готово!** SAPE Reports Panel развернут как независимый сервис на порту 5007 🚀
