# 🔐 Настройка нового сервера IONOS (74.208.242.125)

## ✅ ШАГ 1: Добавить SSH-ключ на сервер

### Публичный ключ (скопирован в буфер обмена):
```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPRzzg8BdBVRVpXKm+7+uRGzJcrBKV/2cujY/zweYg/a ionos-new-server-74.208.242.125
```

### Как добавить на сервер:

**Вариант 1 - Через панель IONOS:**
1. Откройте панель управления IONOS
2. Найдите сервер 74.208.242.125
3. Перейдите в раздел SSH Keys
4. Добавьте публичный ключ (Cmd+V)

**Вариант 2 - Через SSH (если есть доступ по паролю):**
```bash
# Подключитесь к серверу
ssh root@74.208.242.125

# Добавьте публичный ключ
mkdir -p ~/.ssh
echo "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPRzzg8BdBVRVpXKm+7+uRGzJcrBKV/2cujY/zweYg/a ionos-new-server-74.208.242.125" >> ~/.ssh/authorized_keys
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

---

## ✅ ШАГ 2: Настроить GitHub Secret

### 1. Откройте GitHub Secrets:
👉 https://github.com/annbezk777/reports/settings/secrets/actions

### 2. Создайте/обновите IONOS_SSH_KEY:

**Если секрет уже существует:**
- Нажмите на **IONOS_SSH_KEY**
- Нажмите **Update secret**
- Вставьте новый приватный ключ (он будет скопирован в буфер на следующем шаге)

**Если секрета нет:**
- Нажмите **New repository secret**
- Name: `IONOS_SSH_KEY`
- Value: (будет вставлен на следующем шаге)

### 3. Скопируйте приватный ключ:

Выполните команду:
```bash
cat ~/.ssh/ionos_new_server | pbcopy
```

Затем в GitHub: Cmd+V в поле "Secret" → **Add secret** (или **Update secret**)

---

## ✅ ШАГ 3: Проверьте другие секреты

Убедитесь что эти секреты установлены правильно:

| Секрет | Значение |
|--------|----------|
| **IONOS_HOST** | `74.208.242.125` |
| **IONOS_USER** | `root` |
| **DEPLOY_PATH** | `/root/web-projects/sape-reports` |

---

## 🎯 ШАГ 4: Проверка подключения

После добавления ключа на сервер, проверьте подключение:

```bash
ssh ionos-sape-new
```

Должно подключиться **БЕЗ ЗАПРОСА ПАРОЛЯ**.

Если всё работает → ✅ готово к деплою!

---

## 📝 Файлы ключей:

- **Приватный:** `~/.ssh/ionos_new_server`
- **Публичный:** `~/.ssh/ionos_new_server.pub`
- **SSH конфиг:** `~/.ssh/config` (добавлен host: ionos-sape-new)

---

## 🚀 После настройки:

Деплой будет работать автоматически при `git push origin main`!
