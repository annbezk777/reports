# 🚀 Настройка GitHub Secrets для IONOS

Для работы CI/CD нужно добавить секреты в GitHub:

## Шаги настройки:

1. Перейдите в **GitHub** → ваш репозиторий `reports`
2. **Settings** → **Secrets and variables** → **Actions**
3. Нажмите **New repository secret**

## Секреты которые нужно добавить:

### 1. IONOS_SSH_KEY
```
Приватный SSH-ключ для подключения к серверу IONOS
```

**Как получить:**
```bash
cat ~/.ssh/id_rsa
# или
cat ~/.ssh/sape_ionos
```

Скопируйте весь вывод (включая `-----BEGIN` и `-----END`)

---

### 2. IONOS_HOST
```
IP-адрес или домен сервера IONOS
```

**Пример:**
```
69.48.201.233
```

---

### 3. IONOS_USER
```
Пользователь для SSH подключения
```

**Обычно:**
```
root
```

---

### 4. DEPLOY_PATH (опционально)
```
Путь к проекту на сервере
```

**По умолчанию:**
```
/root/web-projects/sape-reports
```

---

## После настройки секретов:

1. ✅ Пуш в main → автоматический деплой
2. ✅ Или вручную: **Actions** → **Deploy to IONOS** → **Run workflow**

## Проверка работы CI/CD:

```bash
# После пуша в main
git push origin main

# Затем на GitHub:
# Actions → Deploy to IONOS → Смотреть логи
```
