# NeuroGraph v8.2 — Changelog

Дата: 2026-02-20
Базовая версия: v8.1 Ultimate

---

## 1. Сохранение настроек WebApp (Пульт Flux)

**Файл:** `templates/index.html`

### Проблема

При повторном открытии Пульта (кнопка «🎛 ОТКРЫТЬ ПУЛЬТ (Flux)») все настройки сбрасывались на дефолтные — модель, промпт, камера, референсы, LoRA терялись.

### Причина

Бот (`bot.py`) уже реализовывал сохранение: при каждом обновлении клавиатуры он кодировал последние настройки из `flux_store` в URL-safe Base64 и вставлял их в URL кнопки WebApp через параметр `?init=`. Однако `index.html` **не содержал кода для чтения этого параметра** — функция `init()` загружала только списки моделей с API, а `?init=` полностью игнорировался.

### Решение

Добавлены две функции в `<script>` секцию `index.html`:

**`getInitData()`** — извлекает и декодирует настройки из URL:
- Читает `?init=` через `URLSearchParams`
- Конвертирует URL-safe Base64 обратно в стандартный (замена `-`→`+`, `_`→`/`, восстановление паддинга `=`)
- Декодирует через `atob()` и парсит JSON
- Возвращает `null` при любой ошибке (первый запуск, битые данные)

**`restoreSettings(d)`** — применяет сохранённый объект ко всем элементам формы:
- **Select-ы моделей:** `ckpt`, `clip`, `vae`, `dtype`, `sage`, `res` — прямое присвоение `.value`
- **Range-слайдеры:** `steps`, `cfg`, `ctx`, `resc`, `rscale` — установка `.value` + обновление текстовых badge-ов через `upd()`
- **Grid-кнопки камеры:** `rot`, `ang`, `dist` — установка скрытого `<input>` + подсветка нужной кнопки через поиск по `onclick`-атрибуту
- **LoRA-стекер:** для каждой сохранённой LoRA вызывается `addLora()`, затем в последний созданный элемент записываются `name` и `weight`
- **Референсы:** установка изображения в `<select>`, активация toggle-кнопок `ON`/`↔️`, выбор rotation
- **Промпты:** `pos` и `neg` textarea, поле `seed`

Вызов происходит в конце `init()` **после** загрузки API и вызова `renderRefs()` — это критично, потому что `<select>` элементы должны быть заполнены `<option>` до того, как `.value` будет установлен. Статус в хедере меняется на «Restored ✓» как визуальная обратная связь.

### Цепочка данных

```
WebApp (send) → tg.sendData(JSON)
    ↓
bot.py (handle_webapp) → d['flux_store'] = data
    ↓
bot.py (get_main_kb) → base64.urlsafe_b64encode(json) → ?init=...
    ↓
Telegram → открывает URL в WebView
    ↓
index.html (init) → getInitData() → restoreSettings()
```

---

## 2. Очистка чата

**Файл:** `bot.py`

### Проблема

Команда «🗑 ОЧИСТИТЬ» удаляла большинство сообщений, но часть системных сообщений бота оставалась в чате — команда `/start`, сообщения WebApp, ошибки генерации.

### Причина

Механизм очистки работает через список `msg_ids` в `user_data`: каждый хендлер должен вызывать `track_message(uid, message_id)` для каждого отправленного или полученного сообщения. Три хендлера пропускали этот вызов:

### Исправления

**`start()`** — не трекалась входящая команда `/start` пользователя:
```python
# Было:
async def start(update, context):
    uid = update.effective_user.id
    msg = await update.message.reply_text(...)  # ← только ответ бота
    track_message(uid, msg.message_id)

# Стало:
async def start(update, context):
    uid = update.effective_user.id
    track_message(uid, update.message.message_id)  # ← + команда пользователя
    msg = await update.message.reply_text(...)
    track_message(uid, msg.message_id)
```

**`handle_webapp()`** — не трекалось входящее WebApp-сообщение (данные из Пульта):
```python
# Было:
async def handle_webapp(update, context):
    uid = update.effective_user.id
    try: ...

# Стало:
async def handle_webapp(update, context):
    uid = update.effective_user.id
    track_message(uid, update.message.message_id)  # ← + WebApp data message
    try: ...
```

**`run_workflow()`** — сообщение об ошибке `Runtime: {e}` отправлялось без трекинга и оставалось навсегда:
```python
# Было:
except Exception as e:
    await context.bot.send_message(uid, f"Runtime: {e}")

# Стало:
except Exception as e:
    m = await context.bot.send_message(uid, f"Runtime: {e}")
    track_message(uid, m.message_id)
```

### Покрытие после исправлений

Все пути отправки сообщений в боте теперь покрыты `track_message`:

| Хендлер | Входящее сообщение | Ответы бота |
|---|---|---|
| `start()` | ✅ | ✅ |
| `handle_photo()` | ✅ (было) | ✅ (было) |
| `handle_webapp()` | ✅ | ✅ (было) |
| `handle_msg()` | ✅ (было) | ✅ (было) |
| `handle_callback()` | N/A (inline) | ✅ (было) |
| `run_workflow()` | N/A | ✅ результаты (было), ✅ ошибки |
| `run_legacy_gen()` | N/A | ✅ (было) |
