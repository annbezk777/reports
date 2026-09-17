# 🔐 Учетные данные проекта

**⚠️ ВАЖНО: Этот файл содержит конфиденциальную информацию. Не публикуйте его в открытом доступе!**

---

## 🌐 SAPE Traffic

### API Токен
```
Токен: c46e580fdafdceeb38c50ee5e49f360d56b8a4bed33754094eb6d726b373e702
Панель: https://traffic.sape.ru/
API Docs: https://traffic.sape.ru/api/doc
```

### API информация
```
API URL: https://traffic.sape.ru/api/v2
Авторизация: Через токен в каждом запросе
Получение статистики: rtb.get_stats
Получение площадок: rtb.get_sites
```

---

## 📊 Google Sheets

### Service Account
```
Email: [будет после настройки - см. google_credentials.json -> client_email]
Файл ключа: google_credentials.json
Права: Editor (Редактор)
```

### Тестовая таблица
```
URL: https://docs.google.com/spreadsheets/d/1rNRwpVMwl9YH-g7gwmzHKGGm4YA2IdrQpoow9ip50dw/edit
Название: Копия PPL // Славянка
Доступ: Нужно добавить Service Account email
```

### Примеры ячеек для метрик
```
Показы (Impressions): B5
Клики (Clicks): C5
CTR: D5
Дата обновления: E5
```

---

## 💻 Локальная панель

### Доступ
```
URL: http://localhost:5005
Порт: 5005
Запуск: python app.py
```

### База данных
```
Тип: SQLite
Путь: /database/sape_reports.db
Создается автоматически
```

---

## 📁 Важные файлы

```
google_credentials.json - Google API ключ (ОБЯЗАТЕЛЬНО!)
sape_reports.db - База данных
config.py - Конфигурация приложения
app.py - Главный файл приложения
```

---

## 🔑 Как получить Service Account Email

После настройки Google API:

```bash
# Открыть файл
cat google_credentials.json | grep client_email

# Или
python -c "import json; print(json.load(open('google_credentials.json'))['client_email'])"
```

Скопировать значение и добавить в каждую Google Sheets таблицу с правами "Editor".

---

## 📝 Пример структуры google_credentials.json

```json
{
  "type": "service_account",
  "project_id": "ваш-проект",
  "private_key_id": "xxxxx",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...",
  "client_email": "bot@your-project.iam.gserviceaccount.com",
  "client_id": "xxxxx",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  ...
}
```

**Важное поле:** `client_email` - это email который нужно добавлять в таблицы!

---

## 🚀 Быстрый запуск

```bash
# Перейти в папку
cd "/Users/annabereznyak/Desktop/Все проекты/api_google sheets"

# Активировать окружение
source venv/bin/activate

# Запустить
python app.py
```

Откроется: http://localhost:5005

---

## 🔄 Добавление нового аккаунта SAPE

В панели:
1. Accounts → Add Account
2. Email: [email]
3. Password: [password]
4. Нажать "Добавить"
5. Нажать "Синхронизировать" для загрузки кампаний

---

## 📊 Создание отчета

В панели:
1. Reports → Create Report
2. Выбрать кампанию
3. Указать Google Sheets URL
4. Указать ячейки (B5, C5, D5 и т.д.)
5. Настроить расписание (дни: 1,5 = Пн,Пт; время: 09:00)
6. Создать
7. Протестировать кнопкой "Обновить сейчас"

---

## ⚠️ Безопасность

**НЕ ПУБЛИКУЙТЕ:**
- google_credentials.json
- CREDENTIALS.md (этот файл)
- Пароли SAPE

**Для продакшена:**
- Используйте переменные окружения
- Шифруйте пароли в базе
- Настройте файрвол для порта 5005

---

**Последнее обновление:** 21.04.2026
**Владелец:** Anna Bereznyak (@ann_bezk)
