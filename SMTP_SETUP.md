# Настройка Email-верификации для SAPE Reports Panel

## 📧 Текущий режим (DEV)

Сейчас коды верификации выводятся в лог сервера для тестирования.

### Как посмотреть код после регистрации:

```bash
ssh root@85.239.51.28 "journalctl -u sape-reports -n 50 | grep 'VERIFICATION CODE'"
```

---

## 🚀 Production настройка (отправка email)

Для отправки реальных email нужно настроить SMTP сервер.

### Вариант 1: Gmail

1. Создайте App Password в Gmail:
   - Перейдите: https://myaccount.google.com/apppasswords
   - Создайте новый пароль приложения
   - Скопируйте 16-значный код

2. Установите переменные окружения на сервере:

```bash
ssh root@85.239.51.28

export SMTP_SERVER="smtp.gmail.com"
export SMTP_PORT="587"
export SMTP_EMAIL="your-email@gmail.com"
export SMTP_PASSWORD="ваш-app-password"

# Перезапустите сервис
systemctl restart sape-reports
```

### Вариант 2: Яндекс

```bash
export SMTP_SERVER="smtp.yandex.ru"
export SMTP_PORT="587"
export SMTP_EMAIL="your-email@yandex.ru"
export SMTP_PASSWORD="ваш-пароль"

systemctl restart sape-reports
```

### Вариант 3: Mail.ru

```bash
export SMTP_SERVER="smtp.mail.ru"
export SMTP_PORT="587"
export SMTP_EMAIL="your-email@mail.ru"
export SMTP_PASSWORD="ваш-пароль"

systemctl restart sape-reports
```

---

## 💾 Постоянная настройка (сохранится после перезагрузки)

Чтобы настройки сохранились после перезагрузки сервера:

```bash
ssh root@85.239.51.28

# Добавьте в файл /etc/environment
sudo nano /etc/environment

# Добавьте строки:
SMTP_SERVER="smtp.gmail.com"
SMTP_PORT="587"
SMTP_EMAIL="your-email@gmail.com"
SMTP_PASSWORD="your-app-password"

# Сохраните (Ctrl+O, Enter, Ctrl+X)

# Перезапустите сервис
systemctl restart sape-reports
```

---

## ✅ Проверка работы

После настройки SMTP:

1. Откройте: http://85.239.51.28:5007/register
2. Зарегистрируйте тестовый аккаунт
3. Проверьте почту - должно прийти письмо с 6-значным кодом
4. Если письмо не пришло - проверьте логи:

```bash
ssh root@85.239.51.28 "journalctl -u sape-reports -n 100 | grep -i 'email\|smtp'"
```

---

## 📝 Формат письма

Пользователь получит письмо:

```
Тема: Подтверждение регистрации - SAPE Reports Panel

Здравствуйте!

Ваш код подтверждения для регистрации в SAPE Reports Panel:

123456

Код действителен в течение 15 минут.

Если вы не регистрировались в системе, проигнорируйте это письмо.

---
SAPE Reports Panel
Автоматизация отчетов SAPE → Google Sheets
```

---

## 🔐 Безопасность

⚠️ **Важно:**
- Используйте App Password, а не основной пароль Gmail
- Не коммитьте пароли в Git
- Храните пароли в переменных окружения
- Регулярно меняйте App Password

---

## 🆘 Troubleshooting

### Письма не отправляются

1. Проверьте переменные окружения:
```bash
ssh root@85.239.51.28 "env | grep SMTP"
```

2. Проверьте логи ошибок:
```bash
ssh root@85.239.51.28 "tail -100 /root/web-projects/sape-reports/logs/error.log | grep -i smtp"
```

3. Попробуйте другой SMTP сервер (Яндекс, Mail.ru)

### Письма в спаме

- Добавьте отправителя в контакты
- Проверьте папку спам при первой регистрации

---

## 📞 Контакты

Если возникли проблемы с настройкой SMTP - свяжитесь с администратором.
