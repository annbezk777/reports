#!/bin/bash
# Скрипт развертывания SAPE Reports на IONOS
# Пользователь: annbezk
# Сервер: 74.208.242.125
# Порт: 5500

set -e

echo "=================================================="
echo "🚀 Развертывание SAPE Reports Panel на IONOS"
echo "=================================================="
echo ""

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Шаг 1: Установка зависимостей${NC}"
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git

echo ""
echo -e "${GREEN}Шаг 2: Клонирование репозитория${NC}"
mkdir -p ~/web-projects
cd ~/web-projects

if [ -d "sape-reports" ]; then
    echo -e "${YELLOW}Директория sape-reports уже существует. Обновляем...${NC}"
    cd sape-reports
    git pull origin main
else
    echo "Клонируем репозиторий..."
    git clone https://github.com/annbezk777/reports.git sape-reports
    cd sape-reports
fi

echo ""
echo -e "${GREEN}Шаг 3: Создание виртуального окружения${NC}"
python3 -m venv venv
source venv/bin/activate

echo ""
echo -e "${GREEN}Шаг 4: Установка Python зависимостей${NC}"
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo -e "${GREEN}Шаг 5: Создание директорий${NC}"
mkdir -p database
mkdir -p logs

echo ""
echo -e "${YELLOW}=================================================${NC}"
echo -e "${YELLOW}⚠️  ВАЖНО: Загрузите файлы вручную!${NC}"
echo -e "${YELLOW}=================================================${NC}"
echo ""
echo "На вашей ЛОКАЛЬНОЙ машине выполните:"
echo ""
echo -e "${GREEN}# 1. Google Sheets credentials${NC}"
echo "scp '/Users/annabereznyak/Desktop/Все проекты/api_google sheets/google_credentials.json' annbezk@74.208.242.125:~/web-projects/sape-reports/"
echo ""
echo -e "${GREEN}# 2. База данных${NC}"
echo "scp '/Users/annabereznyak/Desktop/Все проекты/api_google sheets/database/sape_reports.db' annbezk@74.208.242.125:~/web-projects/sape-reports/database/"
echo ""
echo -e "${YELLOW}Нажмите Enter после загрузки файлов...${NC}"
read -p ""

# Проверка файлов
echo ""
echo -e "${GREEN}Шаг 6: Проверка загруженных файлов${NC}"

if [ ! -f "google_credentials.json" ]; then
    echo -e "${RED}❌ Файл google_credentials.json не найден!${NC}"
    echo "Загрузите его командой выше"
    exit 1
else
    echo -e "${GREEN}✅ google_credentials.json найден${NC}"
fi

if [ ! -f "database/sape_reports.db" ]; then
    echo -e "${RED}❌ Файл database/sape_reports.db не найден!${NC}"
    echo "Загрузите его командой выше"
    exit 1
else
    echo -e "${GREEN}✅ database/sape_reports.db найден${NC}"
fi

echo ""
echo -e "${GREEN}Шаг 7: Настройка systemd сервиса${NC}"

# Создаем модифицированный service файл для пользователя annbezk
cat > /tmp/sape-reports.service << EOF
[Unit]
Description=SAPE Reports Panel
After=network.target

[Service]
Type=notify
User=annbezk
WorkingDirectory=/home/annbezk/web-projects/sape-reports
Environment="PATH=/home/annbezk/web-projects/sape-reports/venv/bin"
Environment="ENABLE_AUTO_SYNC=1"
ExecStart=/home/annbezk/web-projects/sape-reports/venv/bin/gunicorn \
    --workers 4 \
    --bind 0.0.0.0:5500 \
    --timeout 300 \
    --access-logfile /var/log/sape-reports-access.log \
    --error-logfile /var/log/sape-reports-error.log \
    --log-level info \
    wsgi:application
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo cp /tmp/sape-reports.service /etc/systemd/system/

# Создаем лог-файлы и даем права
sudo touch /var/log/sape-reports-access.log
sudo touch /var/log/sape-reports-error.log
sudo chown annbezk:annbezk /var/log/sape-reports-access.log
sudo chown annbezk:annbezk /var/log/sape-reports-error.log

echo ""
echo -e "${GREEN}Шаг 8: Проверка порта 5500${NC}"
if sudo netstat -tulpn | grep -q ":5500 "; then
    echo -e "${RED}⚠️  Порт 5500 уже занят!${NC}"
    sudo netstat -tulpn | grep ":5500"
    echo ""
    read -p "Продолжить? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Отменено"
        exit 1
    fi
else
    echo -e "${GREEN}✅ Порт 5500 свободен${NC}"
fi

echo ""
echo -e "${GREEN}Шаг 9: Запуск сервиса${NC}"
sudo systemctl daemon-reload
sudo systemctl enable sape-reports
sudo systemctl restart sape-reports

echo ""
echo -e "${GREEN}Шаг 10: Проверка статуса${NC}"
sleep 3
sudo systemctl status sape-reports --no-pager

echo ""
echo "=================================================="
echo -e "${GREEN}✅ Развертывание завершено!${NC}"
echo "=================================================="
echo ""
echo "🌐 URL: http://74.208.242.125:5500/"
echo ""
echo "📋 Полезные команды:"
echo ""
echo "  Статус:       sudo systemctl status sape-reports"
echo "  Перезапуск:   sudo systemctl restart sape-reports"
echo "  Логи:         sudo journalctl -u sape-reports -f"
echo "  Логи ошибок:  sudo tail -f /var/log/sape-reports-error.log"
echo ""
echo "🔍 Проверьте что сервис запущен:"
echo "  sudo netstat -tulpn | grep 5500"
echo ""
echo "🎉 Готово! Откройте в браузере: http://74.208.242.125:5500/"
echo ""
