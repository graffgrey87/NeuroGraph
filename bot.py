import os
import sys
import json
import uuid
import time
import random
import asyncio
import traceback
import html
import urllib.request
import urllib.parse
import requests
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# ==========================================
# ⚙️ КОНФИГУРАЦИЯ
# ==========================================
BOT_TOKEN = os.getenv("TG_TOKEN")
# Получаем список админов и чистим от пробелов
raw_ids = os.getenv("ADMIN_ID", "")
ALLOWED_USERS = [int(x) for x in raw_ids.split(",") if x.strip().isdigit()]

# ComfyUI настройки
COMFY_PORT = "3000"
COMFY_SERVER = f"127.0.0.1:{COMFY_PORT}"
BASE_DIR = "/workspace"
CLIENT_ID = str(uuid.uuid4())

# 🔴 WEBAPP НАСТРОЙКИ (FIXED PORT 8099)
RUNPOD_ID = os.environ.get("RUNPOD_POD_ID", "127.0.0.1")
WEBAPP_PORT = "8099"
WEBAPP_URL = f"https://{RUNPOD_ID}-{WEBAPP_PORT}.proxy.runpod.net"

# Режимы работы
WORKFLOWS = {
    "edit": {
        "file": os.path.join(BASE_DIR, "workflow_api.json"), 
        "name": "🎨 Редакт (Img2Img)", 
        "need_photo": True
    },
    "gen": {
        "file": os.path.join(BASE_DIR, "workflow_gen.json"),  
        "name": "✨ Генерация (Txt2Img)", 
        "need_photo": False
    },
    "flux_new": {
        "file": os.path.join(BASE_DIR, "TI2I_Flux2_Klein.json"),
        "name": "🚀 Flux 2 Klein",
        "need_photo": False
    }
}

# Хранилище данных пользователей
user_data = {}

# Проверка токена
if not BOT_TOKEN:
    print("❌ ОШИБКА: Переменная TG_TOKEN не задана!")
    sys.exit(1)

# ==========================================
# 🛠 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================

# --- Умный поиск нод (Smart Fix) ---
def find_node_id(workflow, class_type_list):
    """Ищет ID ноды по типу класса (чтобы не зависеть от жестких ID)"""
    if isinstance(workflow, dict):
        for node_id, node_data in workflow.items():
            if node_data.get("class_type") in class_type_list:
                return node_id
    return None

def get_user_data(uid):
    if uid not in user_data:
        user_data[uid] = {
            'image': None,      # Последнее загруженное фото
            'mode': 'flux_new', # Режим по умолчанию
            'batch': 1,         # Кол-во изображений
            'msg_ids': []       # Для очистки чата
        }
    return user_data[uid]

async def check_auth(update: Update):
    if not ALLOWED_USERS: return True # Если админы не заданы, пускаем всех (опасно, но для теста ок)
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ Извините, этот бот приватный.")
        return False
    return True

# --- API COMFYUI ---
def upload_image(file_bytes, file_name):
    """Загрузка фото в ComfyUI"""
    try:
        files = {'image': (file_name, file_bytes)}
        data = {'type': 'input', 'overwrite': 'true'}
        response = requests.post(f"http://{COMFY_SERVER}/upload/image", files=files, data=data)
        return response.json()
    except Exception as e:
        print(f"Upload Error: {e}")
        return None

def queue_prompt(prompt_workflow):
    """Отправка задачи в очередь"""
    p = {"prompt": prompt_workflow, "client_id": CLIENT_ID}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request(f"http://{COMFY_SERVER}/prompt", data=data)
    return json.loads(urllib.request.urlopen(req).read())

def get_history(prompt_id):
    """Получение истории генерации"""
    try:
        with urllib.request.urlopen(f"http://{COMFY_SERVER}/history/{prompt_id}") as response:
            return json.loads(response.read())
    except: return {}

def get_view(filename, subfolder, folder_type):
    """Скачивание готового изображения"""
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen(f"http://{COMFY_SERVER}/view?{url_values}") as response:
        return response.read()

# --- ЛОГИКА ГЕНЕРАЦИИ И ОЖИДАНИЯ ---
async def monitor_generation(context, uid, prompt_id, batch_size, start_ts, status_msg):
    """Следит за процессом и отправляет результат"""
    try:
        while True:
            h = get_history(prompt_id)
            if prompt_id in h: break
            await asyncio.sleep(1)
        
        dur = time.time() - start_ts
        out = h[prompt_id]['outputs']
        found = False
        
        # Пытаемся найти изображения в выходах всех нод
        for nid in out:
            if 'images' in out[nid]:
                for i, img in enumerate(out[nid]['images']):
                    idata = get_view(img['filename'], img['subfolder'], img['type'])
                    caption = f"⏱ {dur:.1f}s | Batch: {i+1}/{batch_size}"
                    await context.bot.send_photo(uid, idata, caption=caption)
                    found = True
        
        # Удаляем сообщение "Генерирую..."
        try: await status_msg.delete()
        except: pass

        if not found:
            await context.bot.send_message(uid, "⚠️ ComfyUI завершил задачу, но изображений не вернул.")
        else:
            await context.bot.send_message(uid, "✅ Готово!")

    except Exception as e:
        await context.bot.send_message(uid, f"❌ Ошибка при получении результата: {e}")
        traceback.print_exc()

# ==========================================
# 🎮 ОБРАБОТЧИКИ (HANDLERS)
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    uid = update.effective_user.id
    user = get_user_data(uid)
    
    # Клавиатура
    kb = [
        [KeyboardButton("⚙️ Flux Настройки", web_app=WebAppInfo(url=WEBAPP_URL))],
        [KeyboardButton("🖼 Мой режим: " + WORKFLOWS[user['mode']]['name'])],
        [KeyboardButton("🗑 ОЧИСТИТЬ ЧАТ")]
    ]
    markup = ReplyKeyboardMarkup(kb, resize_keyboard=True)
    
    await update.message.reply_text(
        f"🤖 **NeuroGraph Bot v5.5 (Fixed)**\n"
        f"🆔 Pod ID: `{RUNPOD_ID}`\n"
        f"🔌 WebApp Port: `{WEBAPP_PORT}`\n\n"
        f"Нажми кнопку настроек для запуска Flux.",
        reply_markup=markup,
        parse_mode="Markdown"
    )

# --- ОБРАБОТКА ДАННЫХ ИЗ WEBAPP (FLUX) ---
async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    uid = update.effective_user.id
    
    try:
        # 1. Получаем данные от WebApp
        data = json.loads(update.effective_message.web_app_data.data)
        
        # 2. Загружаем Workflow Flux
        cfg = WORKFLOWS["flux_new"]
        if not os.path.exists(cfg['file']):
            await update.message.reply_text(f"❌ Ошибка: Файл {cfg['file']} не найден на сервере!")
            return

        with open(cfg['file'], "r", encoding="utf-8") as f:
            wf = json.load(f)

        # 3. SMART INJECTION (Умная подстановка данных)
        
        # -- Checkpoint --
        ckpt_node = find_node_id(wf, ["DiffusionModelLoader", "CheckpointLoaderSimple", "CheckpointLoader", "DualCLIPLoader"])
        if ckpt_node and "checkpoint" in data:
            # Разные ноды используют разные ключи (model_name или ckpt_name)
            inputs = wf[ckpt_node]["inputs"]
            if "model_name" in inputs: inputs["model_name"] = data["checkpoint"]
            elif "ckpt_name" in inputs: inputs["ckpt_name"] = data["checkpoint"]
        
        # -- Seed --
        seed_node = find_node_id(wf, ["EasySeed", "Seed", "KSampler", "KSamplerAdvanced"])
        if seed_node:
            wf[seed_node]["inputs"]["seed"] = random.randint(1, 10**15)

        # -- LoRA --
        if data.get("lora_1") and data["lora_1"] != "None":
            # Ищем Power Lora (у нее сложная структура)
            plora = find_node_id(wf, ["Power Lora Loader (rgthree)"])
            # Ищем обычную Lora
            slora = find_node_id(wf, ["LoraLoader", "LoraLoaderModelOnly"])
            
            weight = float(data.get("weight_1", 1.0))
            
            if plora:
                wf[plora]["inputs"]["lora_1"] = {"on": True, "lora": data["lora_1"], "strength": weight}
            elif slora:
                wf[slora]["inputs"]["lora_name"] = data["lora_1"]
                wf[slora]["inputs"]["strength_model"] = weight

        # -- Сохраняем и запускаем --
        status_msg = await update.message.reply_text(f"🚀 Запускаю Flux...\nCP: {data.get('checkpoint')}\nLoRA: {data.get('lora_1')}")
        
        res = queue_prompt(wf)
        
        if 'error' in res:
            await status_msg.edit_text(f"❌ Ошибка ComfyUI: {res['error']}")
            return

        # Запускаем мониторинг
        asyncio.create_task(monitor_generation(context, uid, res['prompt_id'], 1, time.time(), status_msg))

    except Exception as e:
        await update.message.reply_text(f"❌ Критическая ошибка бота: {e}")
        traceback.print_exc()

# --- ОБРАБОТКА ТЕКСТА (Смена режимов, очистка) ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    text = update.message.text
    uid = update.effective_user.id
    user = get_user_data(uid)

    if text == "🗑 ОЧИСТИТЬ ЧАТ":
        await update.message.reply_text("История очищена (визуально).")
        # Тут можно добавить логику удаления сообщений, если нужно
    
    elif "Мой режим" in text:
        # Переключалка режимов (циклическая)
        modes = list(WORKFLOWS.keys())
        current_idx = modes.index(user['mode'])
        next_idx = (current_idx + 1) % len(modes)
        user['mode'] = modes[next_idx]
        await start(update, context) # Обновляем клавиатуру
        
    else:
        await update.message.reply_text("Используйте меню для управления.")

# --- ОБРАБОТКА ФОТО (Для старых режимов img2img) ---
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    uid = update.effective_user.id
    user = get_user_data(uid)
    
    # Если режим Flux, говорим, что фото пока не нужно (или можно допилить)
    if user['mode'] == 'flux_new':
        await update.message.reply_text("В режиме Flux отправка фото напрямую пока не используется. Используйте кнопку настроек.")
        return

    # Логика загрузки фото для старых режимов
    photo_file = await update.message.photo[-1].get_file()
    file_bytes = await photo_file.download_as_bytearray()
    
    msg = await update.message.reply_text("📤 Загружаю фото в ComfyUI...")
    resp = upload_image(file_bytes, f"user_{uid}.png")
    
    if resp:
        user['image'] = resp['name']
        await msg.edit_text(f"✅ Фото сохранено как {resp['name']}. Теперь запустите генерацию через меню.")
    else:
        await msg.edit_text("❌ Ошибка загрузки фото.")


if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Регистрируем хендлеры
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
    
    print(f"✅ Bot Started. WebApp URL: {WEBAPP_URL}")
    app.run_polling()
