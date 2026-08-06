# ⚡ Шпаргалка SAPE Reports Panel

## 🚀 Быстрый запуск (3 команды)

```bash
cd "/Users/annabereznyak/Desktop/Все проекты/api_google sheets"
source venv/bin/activate
python app.py
```

Откройте: **http://localhost:5005**

---

## 🔑 Учетные данные

### SAPE API
```
Токен: c46e580fdafdceeb38c50ee5e49f360d56b8a4bed33754094eb6d726b373e702
```

### Google Sheets
```
Service Account: см. google_credentials.json → client_email
Тестовая таблица: https://docs.google.com/spreadsheets/d/1rNRwpVMwl9YH-g7gwmzHKGGm4YA2IdrQpoow9ip50dw/edit
```

---

## 📝 Быстрые команды

### Установка (первый раз)
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Получить Service Account Email
```bash
cat google_credentials.json | grep client_email
```

### Тест Google API
```bash
python -c "from app.api.google_sheets_client import GoogleSheetsClient; from config import Config; c = GoogleSheetsClient(Config.GOOGLE_CREDENTIALS_FILE, Config.GOOGLE_SCOPES); print('✅ OK' if c.authenticate() else '❌ Error')"
```

### Создать БД вручную
```bash
python -c "from app import app, db; app.app_context().push(); db.create_all(); print('✅ Database created')"
```

---

## 📊 Структура таблицы

| A          | B      | C       | D      | E                |
|------------|--------|---------|--------|------------------|
| Метрика    | Значение |       |        |                  |
| Показы     | 1000   |         |        |                  |
| Клики      |        | 50      |        |                  |
| CTR        |        |         | 5.0%   |                  |
| Обновлено  |        |         |        | 21.04.2026 10:00 |

**Ячейки:** B5, C5, D5, E5

---

## 🔄 Расписание

```
Формат дней: 1,5 (понедельник, пятница)
1 = Пн, 2 = Вт, 3 = Ср, 4 = Чт, 5 = Пт, 6 = Сб, 7 = Вс

Формат времени: 09:00
```

---

## ❗ Частые ошибки

### "Invalid credentials"
→ Проверить email/пароль SAPE

### "Permission denied" (Google)
→ Добавить Service Account в таблицу с правами "Editor"

### "File not found: google_credentials.json"
→ Скопировать JSON ключ в корень проекта

---

## 📞 Поддержка

Telegram: @ann_bezk
Email: anna_bereznyak@mail.ru

---

## 📚 Документация

- **INDEX.md** - Навигация по всем файлам
- **GOOGLE_API_SETUP.md** - Настройка Google API
- **QUICK_START.md** - Полный гайд запуска
- **CREDENTIALS.md** - Все логины/пароли
- **ROADMAP.md** - План развития
