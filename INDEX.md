# 📚 Навигация по проекту SAPE Reports Panel

## 🚀 Быстрый старт

**Новичок?** Начните здесь:
1. [GOOGLE_API_SETUP.md](GOOGLE_API_SETUP.md) - Настройка Google API (10 минут)
2. [QUICK_START.md](QUICK_START.md) - Запуск панели (5 минут)
3. [CREDENTIALS.md](CREDENTIALS.md) - Все логины и пароли

**Опытный пользователь?** Сразу к делу:
```bash
cd "/Users/annabereznyak/Desktop/Все проекты/api_google sheets"
source venv/bin/activate
python app.py
# Откройте: http://localhost:5005
```

---

## 📖 Документация

### Основная документация

| Файл | Описание | Для кого |
|------|----------|----------|
| [README.md](README.md) | Полная документация проекта | Все |
| [QUICK_START.md](QUICK_START.md) | Быстрый запуск за 5 минут | Новички |
| [ROADMAP.md](ROADMAP.md) | Дорожная карта и этапы | Планирование |
| [INDEX.md](INDEX.md) | Этот файл - навигация | Навигация |

### Настройка и конфигурация

| Файл | Описание | Когда использовать |
|------|----------|-------------------|
| [GOOGLE_API_SETUP.md](GOOGLE_API_SETUP.md) | Настройка Google Sheets API | Первый запуск |
| [CREDENTIALS.md](CREDENTIALS.md) | Учетные данные (логины/пароли) | Постоянно |
| [config.py](config.py) | Конфигурация приложения | Кастомизация |

### Технические файлы

| Файл | Описание |
|------|----------|
| [requirements.txt](requirements.txt) | Python зависимости |
| [app.py](app.py) | Главный файл Flask |
| [.gitignore](.gitignore) | Игнорируемые файлы Git |

---

## 🗂️ Структура проекта

```
api_google sheets/
│
├── 📄 Документация
│   ├── INDEX.md              ← Вы здесь
│   ├── README.md             ← Полное руководство
│   ├── QUICK_START.md        ← Быстрый старт
│   ├── ROADMAP.md            ← Дорожная карта
│   ├── GOOGLE_API_SETUP.md   ← Настройка Google API
│   └── CREDENTIALS.md        ← Учетные данные (не коммитить!)
│
├── 🔧 Конфигурация
│   ├── config.py             ← Настройки приложения
│   ├── requirements.txt      ← Python пакеты
│   └── .gitignore           ← Игнор файлы
│
├── 💻 Приложение
│   ├── app.py               ← Главный файл Flask
│   ├── app/
│   │   ├── models.py        ← Модели БД
│   │   ├── api/
│   │   │   ├── sape_client.py          ← SAPE API клиент
│   │   │   └── google_sheets_client.py ← Google Sheets клиент
│   │   └── templates/       ← HTML шаблоны
│   │       ├── base.html
│   │       ├── index.html
│   │       ├── accounts.html
│   │       ├── add_account.html
│   │       ├── reports.html
│   │       └── add_report.html
│
├── 🗄️ Данные (создается автоматически)
│   ├── database/
│   │   └── sape_reports.db  ← SQLite база
│   └── migrations/          ← Миграции БД
│
└── 🔑 Секреты (НЕ коммитить!)
    └── google_credentials.json  ← Google API ключ
```

---

## 🎯 Сценарии использования

### Сценарий 1: Первая настройка (новый пользователь)

1. ✅ Прочитать [GOOGLE_API_SETUP.md](GOOGLE_API_SETUP.md)
2. ✅ Настроить Google Sheets API (10 мин)
3. ✅ Скачать `google_credentials.json`
4. ✅ Открыть [QUICK_START.md](QUICK_START.md)
5. ✅ Установить зависимости
6. ✅ Запустить приложение
7. ✅ Создать первый отчет

**Время:** ~30 минут

---

### Сценарий 2: Ежедневная работа

1. Запустить панель: `python app.py`
2. Открыть http://localhost:5005
3. Проверить статус отчетов
4. Обновить отчеты кнопкой "Обновить сейчас"
5. Добавить новые кампании при необходимости

**Время:** ~5 минут/день

---

### Сценарий 3: Добавление нового клиента

1. Открыть [CREDENTIALS.md](CREDENTIALS.md)
2. Получить учетные данные SAPE клиента
3. В панели: Accounts → Add Account
4. Синхронизировать кампании
5. Создать Google Sheets для клиента
6. Дать доступ Service Account
7. Создать отчеты для каждой кампании
8. Протестировать

**Время:** ~15 минут/клиент

---

### Сценарий 4: Устранение проблем

1. Проверить [ROADMAP.md](ROADMAP.md) → Известные проблемы
2. Проверить логи на главной странице панели
3. Проверить [GOOGLE_API_SETUP.md](GOOGLE_API_SETUP.md) → Решение проблем
4. Проверить [QUICK_START.md](QUICK_START.md) → Решение проблем
5. Написать в Telegram: @ann_bezk

---

## 🔗 Полезные ссылки

### Внешние ресурсы

| Ресурс | URL | Для чего |
|--------|-----|----------|
| SAPE Traffic | https://traffic.sape.ru/ | Вход в кабинет |
| SAPE API Docs | https://traffic.sape.ru/api/doc | API документация |
| Google Cloud Console | https://console.cloud.google.com/ | Управление API |
| Тестовая таблица | [Ссылка](https://docs.google.com/spreadsheets/d/1rNRwpVMwl9YH-g7gwmzHKGGm4YA2IdrQpoow9ip50dw/edit) | Пример отчета |

### Локальные ссылки

| Ресурс | URL | Описание |
|--------|-----|----------|
| Панель управления | http://localhost:5005 | Главная |
| Аккаунты SAPE | http://localhost:5005/accounts | Управление |
| Отчеты | http://localhost:5005/reports | Настройка |

---

## 📞 Поддержка

### Контакты разработчика

**Anna Bereznyak**
- 💬 Telegram: @ann_bezk
- 📧 Email: anna_bereznyak@mail.ru
- 📱 WhatsApp: +7 931 287-79-10

### Что делать при ошибке?

1. **Проверить документацию** - раздел "Решение проблем"
2. **Проверить логи** - главная страница панели
3. **Написать в Telegram** - @ann_bezk с описанием ошибки

---

## ⚡ Частые вопросы (FAQ)

### Q: Где найти логины и пароли?
**A:** [CREDENTIALS.md](CREDENTIALS.md)

### Q: Как настроить Google API?
**A:** [GOOGLE_API_SETUP.md](GOOGLE_API_SETUP.md)

### Q: Как запустить панель?
**A:** [QUICK_START.md](QUICK_START.md) раздел "Шаг 3"

### Q: Где дорожная карта развития?
**A:** [ROADMAP.md](ROADMAP.md)

### Q: Как добавить новый аккаунт SAPE?
**A:** [QUICK_START.md](QUICK_START.md) раздел "Шаг 4.1"

### Q: Как создать отчет?
**A:** [QUICK_START.md](QUICK_START.md) раздел "Шаг 4.3"

### Q: Почему данные не обновляются автоматически?
**A:** Автоматический запуск по расписанию пока не реализован. См. [ROADMAP.md](ROADMAP.md) Этап 6.

### Q: Как добавить Service Account в таблицу?
**A:** [GOOGLE_API_SETUP.md](GOOGLE_API_SETUP.md) Шаг 8

---

## 📊 Статус проекта

| Компонент | Статус | Документация |
|-----------|--------|--------------|
| SAPE API клиент | ✅ Готов | [app/api/sape_client.py](app/api/sape_client.py) |
| Google Sheets клиент | ✅ Готов | [app/api/google_sheets_client.py](app/api/google_sheets_client.py) |
| Web панель | ✅ Готов | [app.py](app.py) |
| База данных | ✅ Готов | [app/models.py](app/models.py) |
| Автоматизация | 🔴 В планах | [ROADMAP.md](ROADMAP.md) Этап 6 |
| Email уведомления | 🔴 В планах | [ROADMAP.md](ROADMAP.md) Этап 6 |

---

## 🎓 Обучающие материалы

### Для начинающих

1. Прочитать [README.md](README.md) - общий обзор
2. Пройти [QUICK_START.md](QUICK_START.md) - практика
3. Изучить [ROADMAP.md](ROADMAP.md) - понять план

### Для продвинутых

1. Изучить `app/api/sape_client.py` - SAPE API
2. Изучить `app/api/google_sheets_client.py` - Google API
3. Изучить `app/models.py` - структура БД
4. Модифицировать под свои нужды

---

## 🔄 Последние обновления

**21.04.2026**
- ✅ Создана базовая структура проекта
- ✅ Реализован SAPE API клиент
- ✅ Реализован Google Sheets клиент
- ✅ Создан веб-интерфейс
- ✅ Написана документация

**Следующие шаги:** См. [ROADMAP.md](ROADMAP.md)

---

## 📝 Чек-лист для нового пользователя

- [ ] Прочитал [README.md](README.md)
- [ ] Настроил Google API по [GOOGLE_API_SETUP.md](GOOGLE_API_SETUP.md)
- [ ] Получил `google_credentials.json`
- [ ] Установил зависимости (`pip install -r requirements.txt`)
- [ ] Запустил панель (`python app.py`)
- [ ] Добавил первый аккаунт SAPE
- [ ] Синхронизировал кампании
- [ ] Создал первый отчет
- [ ] Протестировал обновление

---

**Готовы начать?** → [GOOGLE_API_SETUP.md](GOOGLE_API_SETUP.md)

**Вопросы?** → Telegram: @ann_bezk

---

**Версия:** 1.0.0
**Дата:** 21.04.2026
**Проект:** SAPE Reports Panel
