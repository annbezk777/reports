# 🔧 Пошаговая настройка Google Sheets API

## 📝 Что мы будем делать

1. Создать проект в Google Cloud
2. Включить Google Sheets API
3. Создать Service Account
4. Скачать JSON ключ
5. Дать доступ к таблицам

**Время:** ~10 минут

---

## Шаг 1: Открыть Google Cloud Console

1. Откройте в браузере: https://console.cloud.google.com/

2. Войдите под своим Google аккаунтом (если еще не вошли)

---

## Шаг 2: Создать новый проект

1. В верхней части страницы найдите выпадающий список с названием проекта

2. Нажмите на него

3. В открывшемся окне нажмите **"NEW PROJECT"** (или "Создать проект")

4. Заполните форму:
   ```
   Project name: SAPE Reports Panel
   Location: No organization (или оставьте как есть)
   ```

5. Нажмите **"CREATE"** (Создать)

6. Подождите 10-20 секунд пока проект создается

7. Убедитесь что новый проект выбран в верхней панели

---

## Шаг 3: Включить Google Sheets API

1. В боковом меню слева найдите **"APIs & Services"** → **"Library"**

   Или перейдите по прямой ссылке:
   https://console.cloud.google.com/apis/library

2. В поиске вверху введите: **"Google Sheets API"**

3. Кликните на **"Google Sheets API"** в результатах

4. Нажмите большую синюю кнопку **"ENABLE"** (Включить)

5. Подождите пару секунд

✅ **Результат:** API включен!

---

## Шаг 4: Создать Service Account

1. В боковом меню слева выберите **"APIs & Services"** → **"Credentials"**

   Или перейдите:
   https://console.cloud.google.com/apis/credentials

2. Вверху страницы нажмите **"+ CREATE CREDENTIALS"**

3. Выберите **"Service Account"** из выпадающего списка

4. Заполните форму первого шага:
   ```
   Service account name: sape-reports-bot
   Service account ID: sape-reports-bot (заполнится автоматически)
   Service account description: Bot for SAPE reports automation
   ```

5. Нажмите **"CREATE AND CONTINUE"**

6. На втором шаге (Grant this service account access to project):
   - **Пропустите этот шаг** - роли не нужны
   - Нажмите **"CONTINUE"**

7. На третьем шаге (Grant users access to this service account):
   - **Пропустите этот шаг**
   - Нажмите **"DONE"**

✅ **Результат:** Service Account создан!

---

## Шаг 5: Скачать JSON ключ

1. На странице "Credentials" найдите раздел **"Service Accounts"**

2. Найдите в списке созданный Service Account: **sape-reports-bot@...**

3. Кликните на email Service Account

4. Перейдите на вкладку **"KEYS"** (Ключи)

5. Нажмите **"ADD KEY"** → **"Create new key"**

6. Выберите тип ключа: **JSON**

7. Нажмите **"CREATE"**

8. JSON файл автоматически скачается на ваш компьютер
   - Название примерно: `sape-reports-panel-xxxxx-yyyyyyy.json`

✅ **Результат:** JSON ключ скачан!

---

## Шаг 6: Сохранить ключ в проект

1. Откройте папку загрузок на вашем компьютере

2. Найдите скачанный JSON файл

3. **Переместите** его в папку проекта и **переименуйте**:

```bash
# В терминале выполните:
mv ~/Downloads/sape-reports-panel-*.json "/Users/annabereznyak/Desktop/Все проекты/api_google sheets/google_credentials.json"
```

Или вручную:
- Скопируйте файл в `/Users/annabereznyak/Desktop/Все проекты/api_google sheets/`
- Переименуйте в `google_credentials.json`

4. **Проверьте** что файл на месте:

```bash
ls -la "/Users/annabereznyak/Desktop/Все проекты/api_google sheets/google_credentials.json"
```

Должно вывести что-то вроде:
```
-rw-r--r--  1 annabereznyak  staff  2345 Apr 21 10:00 google_credentials.json
```

✅ **Результат:** Ключ сохранен в проекте!

---

## Шаг 7: Получить Service Account Email

1. Откройте файл `google_credentials.json` в любом текстовом редакторе

2. Найдите строку с `"client_email"`:

```json
{
  "type": "service_account",
  "project_id": "sape-reports-panel",
  "private_key_id": "xxxxx",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...",
  "client_email": "sape-reports-bot@sape-reports-panel.iam.gserviceaccount.com",
  ...
}
```

3. **Скопируйте** значение `client_email`

Пример:
```
sape-reports-bot@sape-reports-panel.iam.gserviceaccount.com
```

4. **Сохраните** этот email - он понадобится для каждой Google Sheets таблицы!

---

## Шаг 8: Дать доступ к Google Sheets таблице

Теперь для **КАЖДОЙ** таблицы куда вы хотите писать данные:

### Вариант А: Тестовая таблица (из примера)

1. Откройте таблицу:
   https://docs.google.com/spreadsheets/d/1rNRwpVMwl9YH-g7gwmzHKGGm4YA2IdrQpoow9ip50dw/edit

2. Нажмите кнопку **"Share"** (Настройки доступа) в правом верхнем углу

3. В поле "Add people and groups" вставьте:
   ```
   sape-reports-bot@sape-reports-panel.iam.gserviceaccount.com
   ```
   (ваш email из шага 7)

4. Убедитесь что права установлены на **"Editor"** (Редактор)

5. **СНИМИТЕ** галочку "Notify people" (чтобы не отправлять уведомление)

6. Нажмите **"Share"** или **"Done"**

✅ **Готово!** Бот теперь может писать в эту таблицу

### Вариант Б: Своя таблица

1. Создайте новую Google Sheets таблицу или откройте существующую

2. Повторите шаги из Варианта А

---

## 🎉 Проверка настройки

Проверим что все работает:

```bash
cd "/Users/annabereznyak/Desktop/Все проекты/api_google sheets"

# Активировать виртуальное окружение
source venv/bin/activate

# Запустить тест
python -c "
from app.api.google_sheets_client import GoogleSheetsClient
from config import Config

client = GoogleSheetsClient(
    credentials_file=Config.GOOGLE_CREDENTIALS_FILE,
    scopes=Config.GOOGLE_SCOPES
)

# Тест аутентификации
if client.authenticate():
    print('✅ Google Sheets API настроен правильно!')

    # Тест доступа к таблице
    test_url = 'https://docs.google.com/spreadsheets/d/1rNRwpVMwl9YH-g7gwmzHKGGm4YA2IdrQpoow9ip50dw/edit'
    if client.test_access(test_url):
        print('✅ Доступ к таблице есть!')
    else:
        print('❌ Нет доступа к таблице. Проверьте что Service Account добавлен.')
else:
    print('❌ Ошибка аутентификации. Проверьте google_credentials.json')
"
```

**Ожидаемый результат:**
```
✅ Google Sheets API настроен правильно!
✅ Доступ к таблице есть!
```

---

## ❌ Решение проблем

### Ошибка: "File not found: google_credentials.json"

**Решение:**
```bash
# Проверьте что файл существует
ls -la "/Users/annabereznyak/Desktop/Все проекты/api_google sheets/google_credentials.json"

# Если нет - скопируйте из Downloads
mv ~/Downloads/sape-reports-*.json "/Users/annabereznyak/Desktop/Все проекты/api_google sheets/google_credentials.json"
```

### Ошибка: "Permission denied" при тесте доступа

**Решение:**
1. Откройте Google Sheets таблицу
2. Проверьте что Service Account email добавлен в настройки доступа
3. Проверьте что права "Editor" (Редактор)

### Ошибка: "API not enabled"

**Решение:**
1. Откройте https://console.cloud.google.com/apis/library
2. Найдите "Google Sheets API"
3. Убедитесь что кнопка "ENABLE" нажата (должна быть "MANAGE")

---

## 📋 Чек-лист

Убедитесь что выполнены все шаги:

- [ ] Создан проект в Google Cloud Console
- [ ] Включен Google Sheets API
- [ ] Создан Service Account
- [ ] Скачан JSON ключ
- [ ] JSON ключ сохранен как `google_credentials.json`
- [ ] Скопирован Service Account email
- [ ] Service Account добавлен в Google Sheets с правами "Editor"
- [ ] Тест аутентификации пройден успешно

---

## 🚀 Что дальше?

После успешной настройки:

1. Запустите панель:
   ```bash
   cd "/Users/annabereznyak/Desktop/Все проекты/api_google sheets"
   source venv/bin/activate
   python app.py
   ```

2. Откройте http://localhost:5005

3. Добавьте аккаунт SAPE

4. Создайте первый отчет!

---

**Нужна помощь?**
- Telegram: @ann_bezk
- Email: anna_bereznyak@mail.ru

**Документация:**
- См. QUICK_START.md для полного руководства
- См. ROADMAP.md для плана развития
