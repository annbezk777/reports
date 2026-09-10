# KPI Dashboard

Веб-приложение для работы с KPI метриками из Google Sheets.

## Возможности

- 📊 Поиск кампаний по account, ID РК, названию
- 📈 Отображение плана и факта по метрикам
- 📅 Данные по неделям
- 🎨 Удобный веб-интерфейс
- 🔍 Поддержка множественных ID кампаний

## Структура проекта

```
kpi_app/
├── app.py                 # Flask приложение
├── kpi_parser.py          # Парсер KPI таблиц из Google Sheets
├── templates/
│   └── index.html        # Веб-интерфейс
└── README.md             # Документация
```

## Установка

1. Установите зависимости:
```bash
pip install flask requests
```

2. Запустите приложение:
```bash
python app.py
```

3. Откройте в браузере:
```
http://localhost:5002
```

## API Endpoints

### POST /api/kpi/search
Поиск кампаний в KPI таблице.

**Параметры:**
```json
{
  "account": "Название аккаунта",
  "campaign_id": "298270",
  "campaign_name": "Название кампании",
  "url": "https://docs.google.com/spreadsheets/d/..." (опционально)
}
```

**Ответ:**
```json
{
  "success": true,
  "campaigns": [
    {
      "name": "Деликатный Москва",
      "account": "Деликатный Москва  рет бан",
      "manager": "Маша",
      "campaign_ids": ["298270", "297426", "297425"],
      "plan": {
        "visits": 256,
        "bounces": 40.0,
        "depth": 1.2,
        "time": 120,
        "robotness": 5.0,
        "pi": 85.0
      },
      "fact": {
        "visits": 0,
        "bounces": 0,
        "depth": 0,
        "time": 0,
        "robotness": 0,
        "pi": 0
      },
      "weeks": [
        {
          "name": "Неделя 1",
          "visits": 389,
          "bounces": 7.0,
          "depth": 0,
          "time": 0,
          "robotness": 0,
          "pi": 0
        }
      ]
    }
  ],
  "total": 1
}
```

### GET /api/kpi/all
Получить все кампании из KPI таблицы.

**Параметры:**
- `url` (опционально) - URL Google Sheets таблицы

**Ответ:**
```json
{
  "success": true,
  "campaigns": [...],
  "total": 4
}
```

## Формат KPI таблицы

Таблица должна иметь следующую структуру:
- Столбец 0: Sales (имя менеджера или "ID РК ...")
- Столбец 3: Account (название кампании)
- Столбец 4: AdOps (менеджер)
- Столбец 5: РК (тип строки: план, за всю рк, неделя 1, и т.д.)
- Столбцы 6-12: метрики (клики, визиты, отказы, глубина, время, роботность, PI)

## Примеры использования

### Поиск по ID кампании
```bash
curl -X POST http://localhost:5002/api/kpi/search \
  -H "Content-Type: application/json" \
  -d '{"campaign_id": "298270"}'
```

### Поиск по названию аккаунта
```bash
curl -X POST http://localhost:5002/api/kpi/search \
  -H "Content-Type: application/json" \
  -d '{"account": "Деликатный"}'
```

### Получить все кампании
```bash
curl http://localhost:5002/api/kpi/all
```

## Тестовая таблица

По умолчанию используется тестовая таблица:
https://docs.google.com/spreadsheets/d/1aIcL9bQR2FPI2VIdXS5ZRbRFpE8bEayJfBx5dbkr8Yo/

Чтобы использовать другую таблицу, передайте параметр `url` в API запросе.

## Разработка

### Тестирование парсера
```bash
python kpi_parser.py
```

### Запуск в режиме разработки
```bash
python app.py
```

Приложение будет доступно на http://localhost:5002

## Технологии

- **Backend:** Flask, Python 3
- **Frontend:** HTML, CSS, JavaScript (Vanilla)
- **Data:** Google Sheets API (export as CSV)
