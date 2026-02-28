# NeuroGraph

Telegram-бот для генерации изображений через **ComfyUI** на **RunPod**.  
Управление генерацией: кнопки Telegram + WebApp «Пульт» → API ComfyUI → результат в чат.

## Стек

| Компонент | Технология |
|---|---|
| Бот | Python, `python-telegram-bot` |
| Генерация | ComfyUI API (Flux 2 Klein 9B) |
| WebApp сервер | FastAPI + Uvicorn |
| Платформа | RunPod (GPU облако, Docker) |

## Режимы генерации

| Режим | Workflow | Описание |
|---|---|---|
| 🚀 Flux Pro | `TI2I_Flux2_Klein.json` | WebApp Пульт, Camera Control, 6 референсов, LoRA-стекер |
| 🎨 Редакт (Qwen) | `workflow_api.json` | Image-to-Image, требует загрузки фото, wildcards |
| ✨ Генерация (Legacy) | `workflow_gen.json` | Text-to-Image, wildcards |

## Порты

| Порт | Сервис |
|---|---|
| 3000 | ComfyUI Backend (API) |
| 8081 | File Browser (comfy-image-saver) |
| 8082 | CivitAI Helper |
| 8083 | Gallery |
| 8099 | WebApp Server (FastAPI) |
| 8888 | Jupyter |

## Переменные окружения

| Переменная | Описание |
|---|---|
| `TG_TOKEN` | Токен Telegram-бота (обязательно) |
| `ADMIN_ID` | ID разрешённых пользователей через запятую |
| `HF_TOKEN` | Hugging Face токен для скачивания моделей |
| `CIVITAI_API_TOKEN` | Токен CivitAI |
| `RUNPOD_POD_ID` | Автодетект RunPod |

## Структура проекта

```
NeuroGraph/
├── bot.py                     # Ядро бота (v8.4)
├── webapp_server.py           # FastAPI-сервер для WebApp Пульта
├── install.sh                 # Автоустановка на RunPod (aria2 turbo)
├── TI2I_Flux2_Klein.json      # Flux workflow
├── workflow_api.json          # Qwen Edit workflow
├── templates/
│   ├── index.html             # WebApp Пульт (Стиль ComfyUI)
│   └── status.html            # WebApp Серверная статистика
├── wildcards/                 # Шаблоны промптов (16 файлов)
└── docs/
    ├── Changelog.md           # История изменений
    ├── TODO.md                # Открытые задачи
    ├── Project_Center_Reference.md  # Справочник режима Qwen Edit
    └── Поясненние к Workflow.txt    # Архитектура Flux-воркфлоу
```

## Быстрый старт (RunPod)

**Container Image:** `smyshnikof/comfyui:base-torch2.8.0-cu128`

**Container Start Command:**
```bash
bash -c "rm -rf /workspace/installer; git clone https://github.com/graffgrey87/NeuroGraph.git /workspace/installer; (while ! curl -s http://localhost:3000 > /dev/null; do sleep 10; done; echo '✅ ComfyUI detected! Waiting 30s...'; sleep 30; bash /workspace/installer/install.sh) & /start.sh"
```

Скрипт `install.sh` автоматически:
1. Дождётся запуска ComfyUI (порт 3000)
2. Установит зависимости (aria2, pip-пакеты)
3. Клонирует custom_nodes
4. Скачает модели (чекпоинты, CLIP, VAE, 27+ LoRA)
5. Скопирует файлы бота и запустит все сервисы