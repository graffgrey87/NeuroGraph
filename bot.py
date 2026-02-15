#!/bin/bash

# ==========================================
# 🚀 УСТАНОВКА НА ПОРТ 8099 (Correct Bind)
# ==========================================

echo "🛑 Останавливаю старые процессы..."
pkill -f "bot.py"
pkill -f "webapp_server.py"

# 1. ЗАПИСЫВАЕМ СЕРВЕР WEBAPP (Strict 0.0.0.0:8099)
# Важно: host="0.0.0.0" обязателен для работы внешнего порта RunPod!
cat << 'EOF' > /workspace/webapp_server.py
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import os
import json

app = FastAPI()

# Папки
BASE_DIR = "/workspace"
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")

if not os.path.exists(TEMPLATE_DIR):
    os.makedirs(TEMPLATE_DIR)

# Создаем HTML шаблон, если его нет
INDEX_HTML = os.path.join(TEMPLATE_DIR, "index.html")
if not os.path.exists(INDEX_HTML):
    with open(INDEX_HTML, "w", encoding="utf-8") as f:
        f.write("<h1>WebApp Error: Template not found. Run installer again.</h1>")

templates = Jinja2Templates(directory=TEMPLATE_DIR)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

if __name__ == "__main__":
    # СЛУШАЕМ ВСЕ ИНТЕРФЕЙСЫ НА ПОРТУ 8099
    uvicorn.run(app, host="0.0.0.0", port=8099)
EOF

# 2. ЗАПИСЫВАЕМ БОТА (Smart Version + Port 8099)
cat << 'EOF' > /workspace/bot.py
import websocket, uuid, json, urllib.request, urllib.parse, requests, random, os, time, traceback, re, sys, html, asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# НАСТРОЙКИ
BOT_TOKEN = os.getenv("TG_TOKEN")
raw_ids = os.getenv("ADMIN_ID")
ALLOWED_USERS = [int(x) for x in raw_ids.split(",") if x.strip().isdigit()] if raw_ids else []

COMFY_PORT = "3000"
RUNPOD_ID = os.environ.get("RUNPOD_POD_ID", "127.0.0.1")
COMFY_SERVER = f"127.0.0.1:{COMFY_PORT}"
BASE_DIR = "/workspace"
CLIENT_ID = str(uuid.uuid4())

# 🔴 ГЛАВНОЕ: ПОРТ 8099
WEBAPP_PORT = "8099"
WEBAPP_URL = f"https://{RUNPOD_ID}-{WEBAPP_PORT}.proxy.runpod.net"

WORKFLOWS = {
    "edit": {"file": os.path.join(BASE_DIR, "workflow_api.json"), "name": "🎨 Редакт (Qwen)", "need_photo": True},
    "gen": {"file": os.path.join(BASE_DIR, "workflow_gen.json"), "name": "✨ Генерация (Old)", "need_photo": False},
    "flux_new": {"file": os.path.join(BASE_DIR, "TI2I_Flux2_Klein.json"), "name": "🚀 Flux 2 Klein", "need_photo": False}
}

user_data = {}

if not BOT_TOKEN:
    print("❌ ОШИБКА: TG_TOKEN не задан!")
    sys.exit(1)

# === SMART FINDER (Авто-поиск нод) ===
def find_node_id(workflow, class_type_list):
    if isinstance(workflow, dict):
        for node_id, node_data in workflow.items():
            if node_data.get("class_type") in class_type_list: return node_id
    return None

async def check_auth(update: Update):
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ Доступ запрещен.")
        return False
    return True

def get_user_data(uid):
    if uid not in user_data:
        user_data[uid] = {
            'image': None, 'mode': 'normal', 'wf': 'edit', 'batch': 1, 
            'dataset_name': 'Batch', 'msg_ids': [], 'loras': {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}, 'awaiting_lora': None
        }
    return user_data[uid]

def track_message(user_id, message_id):
    data = get_user_data(user_id)
    if message_id not in data['msg_ids']:
        data['msg_ids'].append(message_id)
    if len(data['msg_ids']) > 100: data['msg_ids'].pop(0)

def queue_prompt(prompt_workflow):
    p = {"prompt": prompt_workflow, "client_id": CLIENT_ID}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request(f"http://{COMFY_SERVER}/prompt", data=data)
    return json.loads(urllib.request.urlopen(req).read())

def get_history(prompt_id):
    try:
        with urllib.request.urlopen(f"http://{COMFY_SERVER}/history/{prompt_id}") as response:
            return json.loads(response.read())
    except: return {}

def get_view(filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen(f"http://{COMFY_SERVER}/view?{url_values}") as response:
        return response.read()

async def monitor_generation(context, uid, prompt_id, batch_size, start_ts, status_msg_id):
    try:
        while True:
            h = get_history(prompt_id)
            if prompt_id in h: break
            await asyncio.sleep(1)
        
        dur = time.time() - start_ts
        out = h[prompt_id]['outputs']
        found = False
        real_prompt = "Result"
        
        for nid in out:
            if 'text' in out[nid]:
                val = out[nid]['text']
                real_prompt = " ".join([str(x) for x in val]) if isinstance(val, list) else str(val)
                break

        for nid in out:
            if 'images' in out[nid]:
                for i, img in enumerate(out[nid]['images']):
                    idata = get_view(img['filename'], img['subfolder'], img['type'])
                    cap = f"<b>🖼 {i+1}/{batch_size} ({dur:.1f}s)</b>\n\n{html.escape(str(real_prompt)[:900])}"
                    m = await context.bot.send_photo(uid, idata, caption=cap, parse_mode="HTML")
                    track_message(uid, m.message_id)
                    found = True
        
        if not found:
            m = await context.bot.send_message(uid, "⚠️ Нет изображений.")
            track_message(uid, m.message_id)

    except Exception as e:
        await context.bot.send_message(uid, f"Crash: {e}")
        traceback.print_exc()

    try: await context.bot.delete_message(uid, status_msg_id)
    except: pass
    fin = await context.bot.send_message(uid, "🏁 Готово!")
    track_message(uid, fin.message_id)

async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    uid = update.effective_user.id
    try:
        data = json.loads(update.effective_message.web_app_data.data)
        cfg = WORKFLOWS["flux_new"]
        
        if not os.path.exists(cfg['file']):
            await update.message.reply_text(f"❌ Нет файла: {cfg['file']}")
            return

        with open(cfg['file'], "r", encoding="utf-8") as f: wf = json.load(f)

        # 1. Checkpoint
        ckpt = find_node_id(wf, ["DiffusionModelLoader", "CheckpointLoaderSimple", "CheckpointLoader", "DualCLIPLoader"])
        if ckpt and "checkpoint" in data:
            if "model_name" in wf[ckpt]["inputs"]: wf[ckpt]["inputs"]["model_name"] = data["checkpoint"]
            elif "ckpt_name" in wf[ckpt]["inputs"]: wf[ckpt]["inputs"]["ckpt_name"] = data["checkpoint"]

        # 2. Seed
        seed = find_node_id(wf, ["EasySeed", "Seed", "KSampler", "KSamplerAdvanced"])
        if seed: wf[seed]["inputs"]["seed"] = random.randint(1, 10**15)

        # 3. Lora
        if data.get("lora_1") and data["lora_1"] != "None":
            plora = find_node_id(wf, ["Power Lora Loader (rgthree)"])
            slora = find_node_id(wf, ["LoraLoader", "LoraLoaderModelOnly"])
            
            if plora:
                wf[plora]["inputs"]["lora_1"] = {"on": True, "lora": data["lora_1"], "strength": float(data.get("weight_1", 1.0))}
            elif slora:
                wf[slora]["inputs"]["lora_name"] = data["lora_1"]
                wf[slora]["inputs"]["strength_model"] = float(data.get("weight_1", 1.0))

        status = await update.message.reply_text("⚙️ Flux запускается...")
        track_message(uid, status.message_id)
        
        res = queue_prompt(wf)
        if 'error' in res:
            await status.edit_text(f"❌ Comfy Error: {res['error']}")
            return

        await monitor_generation(context, uid, res['prompt_id'], 1, time.time(), status.message_id)

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка WebApp: {e}")
        traceback.print_exc()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    uid = update.effective_user.id
    kb = ReplyKeyboardMarkup([[KeyboardButton("⚙️ Flux Настройки", web_app=WebAppInfo(url=WEBAPP_URL))]], resize_keyboard=True)
    await update.message.reply_text(f"🎛 **NeuroGraph v8.0 (Custom Port)**\nPort: {WEBAPP_PORT}", reply_markup=kb, parse_mode="Markdown")

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))
    print(f"Bot v8.0 Started on {RUNPOD_ID}:{WEBAPP_PORT}")
    app.run_polling()
EOF

# 3. ЗАПУСК
export RUNPOD_POD_ID=$(echo $RUNPOD_POD_ID)

echo "🚀 Запускаю WebApp на 0.0.0.0:8099..."
nohup /workspace/venv/bin/python /workspace/webapp_server.py > /workspace/webapp.log 2>&1 &

echo "🤖 Запускаю Бота..."
nohup /workspace/venv/bin/python /workspace/bot.py > /workspace/bot.log 2>&1 &

echo "✅ ГОТОВО! Проверь в Телеграм."
echo "Если меню не открывается - убедись, что в 'Edit Pod' добавлен порт 8099 (HTTP)."
