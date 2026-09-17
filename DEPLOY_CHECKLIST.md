# 🚀 Чек-лист развертывания SAPE Reports на IONOS

**Сервер:** 69.48.201.233
**Порт:** 5500
**Путь:** /root/web-projects/sape-reports

---

## ✅ Шаг 1: Подготовка локального проекта

### 1.1 Проверить файлы
```bash
cd "/Users/annabereznyak/Desktop/Все проекты/api_google sheets"
ls -la .gitignore wsgi.py requirements.txt sape-reports.service
```

Должны быть:
- ✅ `.gitignore` - исключения для Git
- ✅ `wsgi.py` - точка входа для Gunicorn
- ✅ `requirements.txt` - зависимости
- ✅ `sape-reports.service` - systemd конфиг (порт 5500)

### 1.2 Создать GitHub репозиторий
1. Зайти на https://github.com
2. Создать новый приватный репозиторий: `sape-reports-panel`
3. НЕ добавлять README, .gitignore (уже есть)

### 1.3 Инициализировать Git и загрузить код
```bash
cd "/Users/annabereznyak/Desktop/Все проекты/api_google sheets"

# Инициализация (если еще не сделано)
git init

# Добавить все файлы (кроме исключений из .gitignore)
git add .

# Проверить что НЕ добавлено (должны быть *.db, *.log, credentials.json)
git status

# Коммит
git commit -m "Initial commit: SAPE Reports Panel ready for deployment"

# Добавить remote (замените YOUR_USERNAME на ваш GitHub username)
git remote add origin git@github.com:YOUR_USERNAME/sape-reports-panel.git

# Или через HTTPS:
# git remote add origin https://github.com/YOUR_USERNAME/sape-reports-panel.git

# Push
git branch -M main
git push -u origin main
```

---

## ✅ Шаг 2: Подключение к серверу

### 2.1 Подключиться к IONOS
```bash
ssh root@69.48.201.233
```

**Если нужен SSH ключ:**
```bash
ssh -i ~/.ssh/ionos_sape_reports root@69.48.201.233
```

**Если не работает:** Спросить у администратора пароль или добавить SSH ключ.

### 2.2 Проверить свободные порты
```bash
netstat -tulpn | grep 5500
# Если порт свободен - ничего не выведет
# Если занят - выберите другой порт
```

---

## ✅ Шаг 3: Установка на сервере

### 3.1 Обновить систему и установить пакеты
```bash
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv git
```

### 3.2 Создать директорию и клонировать репозиторий
```bash
mkdir -p /root/web-projects
cd /root/web-projects

# Клонировать (замените YOUR_USERNAME)
git clone https://github.com/YOUR_USERNAME/sape-reports-panel.git sape-reports
cd sape-reports
```

### 3.3 Создать виртуальное окружение
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## ✅ Шаг 4: Загрузить критические файлы

### 4.1 Google Sheets credentials
**На локальной машине** выполнить:
```bash
scp "/Users/annabereznyak/Desktop/Все проекты/api_google sheets/google_credentials.json" root@69.48.201.233:/root/web-projects/sape-reports/
```

### 4.2 База данных
**На локальной машине** выполнить:
```bash
scp "/Users/annabereznyak/Desktop/Все проекты/api_google sheets/database/sape_reports.db" root@69.48.201.233:/root/web-projects/sape-reports/database/
```

### 4.3 Проверить на сервере
```bash
ls -la /root/web-projects/sape-reports/google_credentials.json
ls -la /root/web-projects/sape-reports/database/sape_reports.db
```

---

## ✅ Шаг 5: Настроить systemd сервис

### 5.1 Скопировать service файл
```bash
cp /root/web-projects/sape-reports/sape-reports.service /etc/systemd/system/
```

### 5.2 Проверить конфигурацию
```bash
cat /etc/systemd/system/sape-reports.service
# Должен быть порт 5500
# Должна быть переменная ENABLE_AUTO_SYNC=1
```

### 5.3 Активировать сервис
```bash
systemctl daemon-reload
systemctl enable sape-reports
systemctl start sape-reports
```

### 5.4 Проверить статус
```bash
systemctl status sape-reports
```

Должно быть: `Active: active (running)`

---

## ✅ Шаг 6: Настроить файрвол

```bash
# Проверить файрвол
ufw status

# Открыть порт 5500
ufw allow 5500/tcp

# Проверить
ufw status
```

---

## ✅ Шаг 7: Проверка работы

### 7.1 Проверить что сервис запущен
```bash
netstat -tulpn | grep 5500
```

Должна быть строка:
```
tcp        0      0 0.0.0.0:5500            0.0.0.0:*               LISTEN      PID/gunicorn
```

### 7.2 Проверить логи
```bash
tail -f /var/log/sape-reports-error.log
```

### 7.3 Открыть в браузере
```
http://69.48.201.233:5500/
```

Должна открыться страница входа или главная страница.

### 7.4 Проверить автосинхронизацию
```bash
journalctl -u sape-reports -f
```

Должны быть сообщения о планировщике:
```
✅ Scheduler started: Daily account sync at 10:00 Moscow time
```

---

## ✅ Шаг 8: Тестирование

### 8.1 Войти в систему
- Открыть http://69.48.201.233:5500/
- Войти под существующим пользователем

### 8.2 Проверить аккаунты
- Перейти в раздел "Аккаунты"
- Проверить что все 21 аккаунт загрузились

### 8.3 Проверить отчеты
- Перейти в раздел "Отчеты"
- Должно быть 66 отчетов
- Попробовать обновить один отчет вручную

### 8.4 Проверить расписание
- Создать тестовый отчет с расписанием
- Дождаться автоматического запуска
- Проверить логи

---

## ✅ Шаг 9: Обновление кода в будущем

```bash
# Подключиться к серверу
ssh root@69.48.201.233

# Перейти в директорию
cd /root/web-projects/sape-reports

# Обновить код
git pull origin main

# Перезапустить сервис
systemctl restart sape-reports

# Проверить статус
systemctl status sape-reports
```

---

## 🛠️ Полезные команды

### Просмотр логов в реальном времени
```bash
journalctl -u sape-reports -f
```

### Перезапуск сервиса
```bash
systemctl restart sape-reports
```

### Остановка сервиса
```bash
systemctl stop sape-reports
```

### Проверка статуса
```bash
systemctl status sape-reports
```

### Просмотр ошибок
```bash
tail -100 /var/log/sape-reports-error.log
```

---

## ❓ Решение проблем

### Сервис не запускается
```bash
# Проверить логи
journalctl -u sape-reports -n 100

# Проверить что порт свободен
netstat -tulpn | grep 5500

# Проверить права на файлы
ls -la /root/web-projects/sape-reports/
```

### Ошибка "No module named 'app'"
```bash
cd /root/web-projects/sape-reports
source venv/bin/activate
pip install -r requirements.txt
systemctl restart sape-reports
```

### База данных не найдена
```bash
# Создать директорию
mkdir -p /root/web-projects/sape-reports/database

# Загрузить БД с локальной машины
# (выполнить на локальной машине)
scp "/Users/annabereznyak/Desktop/Все проекты/api_google sheets/database/sape_reports.db" root@69.48.201.233:/root/web-projects/sape-reports/database/
```

### Google Sheets не обновляется
```bash
# Проверить credentials
ls -la /root/web-projects/sape-reports/google_credentials.json

# Загрузить с локальной машины если отсутствует
scp "/Users/annabereznyak/Desktop/Все проекты/api_google sheets/google_credentials.json" root@69.48.201.233:/root/web-projects/sape-reports/
```

---

## 📊 Финальная проверка

- [ ] Сервис запущен: `systemctl status sape-reports`
- [ ] Порт открыт: `netstat -tulpn | grep 5500`
- [ ] Сайт доступен: http://69.48.201.233:5500/
- [ ] Автосинхронизация работает: `journalctl -u sape-reports | grep Scheduler`
- [ ] Отчеты обновляются вручную
- [ ] Логи пишутся: `tail /var/log/sape-reports-error.log`

---

**Готово! 🎉**

Ваша SAPE Reports Panel развернута на сервере и работает 24/7 с автоматическим расписанием!

URL: http://69.48.201.233:5500/
