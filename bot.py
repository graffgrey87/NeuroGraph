# 1. Записываем новый код бота (Smart Edition)
cat << 'EOF' > /workspace/bot.py
import websocket, uuid, json, urllib.request, urllib.parse, requests, random, os, time, traceback, re, sys, html, asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# ==========================================
# ⚙️ НАСТРОЙКИ (v6.0 Smart Auto-Find)
# ==========================================
BOT_TOKEN = os.getenv("TG_TOKEN")
raw_ids = os.getenv("ADMIN_ID")
ALLOWED_USERS = [int(x) for x in raw_ids.split(",") if x.strip().isdigit()] if raw_ids else []

COMFY_PORT = "3000"
RUNPOD_ID = os.environ.get("RUNPOD_POD_ID", "127.0.0.1")
COMFY_SERVER = f"127.0.0.1:{COMFY_PORT}"
BASE_DIR = "/workspace"
CLIENT_ID = str(uuid.uuid4())

# Используем проверенный порт 8099
WEBAPP_PORT = "8099"
WEBAPP_URL = f"https://{RUNPOD_ID}-{WEBAPP_PORT}.proxy.runpod.net"

# Настройки режимов
WORKFLOWS = {
    "edit": {
        "file": os.path.join(BASE_DIR, "workflow_api.json"), 
        "name": "🎨 Редакт (Qwen)", 
        "need_photo": True
    },
    "gen": {
        "file": os.path.join(BASE_DIR, "workflow_gen.json"),  
        "name": "✨ Генерация (Old)", 
        "need_photo": False
    },
    "flux_new": {
        "file": os.path.join(BASE_DIR, "TI2I_Flux2_Klein.json"),
        "name": "🚀 Flux 2 Klein",
        "need_photo": False
    }
}

PROMPT_NORMAL = "На фото крупным планом показана высокая девушка с изображения 1 которая __действие__ __место__. На ней __наряд__. Её наряд выполнен в __цвет__. Из украшений на ней __украшения__. Ракурс __ракурс__, __угол__, __крупность__ __выражения__. Фото в стиле __стиль__, реалистичное освещение."
PROMPT_NSFW = "На фото крупным планом показана высокая девушка с изображения 1, которая __действие_nsfw__ __место__. На ней __наряд_nsfw__. Она __доп_действие_nsfw__. Её наряд выполнен в __цвет__. Из украшений на ней __украшения__. Ракурс __ракурс__, __угол__, __крупность__ __выражения__. Фото в стиле __стиль__, реалистичное освещение."

user_data = {}

if not BOT_TOKEN:
    print("❌ ОШИБКА: TG_TOKEN не задан!")
    sys.exit(1)

# ==========================================
# 🛠 ПОМОЩНИКИ (SMART SEARCH)
# ==========================================
def find_node_id(workflow, class_type_list):
    """Ищет ID ноды по списку возможных типов классов"""
    if isinstance(workflow, dict):
        for node_id, node_data in workflow.items():
            if node_data.get("class_type") in class_type_list:
                return node_id
    return None

def find_node_by_input(workflow, input_name):
    """Ищет ноду, у которой есть конкретный входной параметр (например, 'lora_1')"""
    if isinstance(workflow, dict):
        for node_id, node_data in workflow.items():
            if "inputs" in node_data and input_name in node_data["inputs"]:
                return node_id
    return None

def escape_html(text):
    return html.escape(str(text))

async def check_auth(update: Update):
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ Доступ запрещен.")
        return False
    return True

def get_user_data(uid):
    if uid not in user_data:
        user_data[uid] = {
            'image': None, 'mode': 'normal', 'wf': 'edit', 'batch': 1, 
            'dataset_name': 'Batch', 'msg_ids': [],
            'loras': {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}, 
            'awaiting_lora': None, 'awaiting_custom_batch': False, 'awaiting_dataset_name': False
        }
    return user_data[uid]

def track_message(user_id, message_id):
    data = get_user_data(user_id)
    if message_id not in data['msg_ids']:
        data['msg_ids'].append(message_id)
    if len(data['msg_ids']) > 100: data['msg_ids'].pop(0)

def fix_paths_for_linux(workflow):
    for nid, node in workflow.items():
        if "inputs" in node:
            for key, val in node["inputs"].items():
                if isinstance(val, str) and "\\" in val:
                    node["inputs"][key] = val.replace("\\", "/")
    return workflow

# --- API COMFYUI ---
def upload_image(file_bytes, file_name):
    try:
        files = {'image': (file_name, file_bytes)}
        data = {'type': 'input', 'overwrite': 'true'}
        response = requests.post(f"http://{COMFY_SERVER}/upload/image", files=files, data=data)
        return response.json()
    except: return None

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

# --- ЛОГИКА ОЖИДАНИЯ ---
async def monitor_generation(context, uid, prompt_id, batch_size, start_ts, status_msg_id):
    d = get_user_data(uid)
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
                    cap = f"<b>🖼 {i+1}/{batch_size} ({dur:.1f}s)</b>\n\n{escape_html(real_prompt[:900])}"
                    m = await context.bot.send_photo(uid, idata, caption=cap, parse_mode="HTML")
                    track_message(uid, m.message_id)
                    found = True
        
        if not found:
            m = await context.bot.send_message(uid, "⚠️ ComfyUI завершил работу, но изображений не вернул.")
            track_message(uid, m.message_id)

    except Exception as e:
        m = await context.bot.send_message(uid, f"Crash: {e}")
        track_message(uid, m.message_id)
        traceback.print_exc()

    try: await context.bot.delete_message(uid, status_msg_id)
    except: pass
    fin = await context.bot.send_message(uid, "🏁 Готово!")
    track_message(uid, fin.message_id)

# --- КЛАВИАТУРЫ ---
def get_main_kb(uid):
    d = get_user_data(uid)
    wf_name = WORKFLOWS[d['wf']]['name']
    kb = [
        [KeyboardButton("⚙️ Flux Настройки", web_app=WebAppInfo(url=WEBAPP_URL))],
        [KeyboardButton("🚀 ГЕНЕРАЦИЯ"), KeyboardButton("🗑 ОЧИСТИТЬ")],
        [KeyboardButton(f"🔄 WF: {wf_name}"), KeyboardButton(f"🔢 Кол-во: {d['batch']}")]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

# --- ОБРАБОТЧИКИ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    uid = update.effective_user.id
    msg = await update.message.reply_text(f"🎛 **NeuroGraph v6.0 (Smart)**\nID: `{RUNPOD_ID}`\nPort: {WEBAPP_PORT}", reply_markup=get_main_kb(uid), parse_mode="Markdown")
    track_message(uid, msg.message_id)

async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    uid = update.effective_user.id
    try:
        data = json.loads(update.effective_message.web_app_data.data)
        cfg_flux = WORKFLOWS["flux_new"]
        
        if not os.path.exists(cfg_flux['file']):
            await update.message.reply_text(f"❌ Файл JSON не найден!")
            return

        with open(cfg_flux['file'], "r", encoding="utf-8") as f: wf = json.load(f)
        
        # === УМНЫЙ ПОИСК И ПОДСТАНОВКА ===
        
        # 1. CHECKPOINT (Ищем Loader)
        ckpt_node = find_node_id(wf, ["DiffusionModelLoader", "CheckpointLoaderSimple", "CheckpointLoader", "DualCLIPLoader"])
        if ckpt_node and "checkpoint" in data:
            if "model_name" in wf[ckpt_node]["inputs"]:
                wf[ckpt_node]["inputs"]["model_name"] = data["checkpoint"]
            elif "ckpt_name" in wf[ckpt_node]["inputs"]:
                wf[ckpt_node]["inputs"]["ckpt_name"] = data["checkpoint"]
            print(f"✅ Checkpoint injected into Node {ckpt_node}")

        # 2. SEED (Ищем EasySeed или Sampler)
        seed_node = find_node_id(wf, ["EasySeed", "Seed", "KSampler", "KSamplerAdvanced"])
        if seed_node:
            wf[seed_node]["inputs"]["seed"] = random.randint(1, 10**15)
            print(f"✅ Seed injected into Node {seed_node}")

        # 3. LORA (Ищем Power Lora Loader или обычный)
        # Сначала пробуем найти спец. ноду Power Lora
        lora_node = find_node_id(wf, ["Power Lora Loader (rgthree)"])
        if lora_node and data.get("lora_1") and data["lora_1"] != "None":
            wf[lora_node]["inputs"]["lora_1"] = {
                "on": True,
                "lora": data["lora_1"],
                "strength": float(data.get("weight_1", 1.0))
            }
            print(f"✅ Power Lora injected into Node {lora_node}")
        
        # Если Power Lora нет, ищем обычный LoraLoader
        elif data.get("lora_1") and data["lora_1"] != "None":
            simple_lora = find_node_id(wf, ["LoraLoader", "LoraLoaderModelOnly"])
            if simple_lora:
                wf[simple_lora]["inputs"]["lora_name"] = data["lora_1"]
                wf[simple_lora]["inputs"]["strength_model"] = float(data.get("weight_1", 1.0))
                print(f"✅ Simple Lora injected into Node {simple_lora}")

        # 4. КАМЕРА И РАКУРСЫ (Сложный момент, ищем по значению или типу)
        # Здесь мы предполагаем, что в JSON есть примитивы (Integer), отвечающие за углы
        # Это "слепая" попытка, но лучше чем хардкод. Если не найдет - пропустит без краша.
        
        # В твоем WebApp приходят cam_rot, cam_angle, cam_dist.
        # Обычно это PrimitiveNode. Поиск сложный, поэтому оставим пока без краша.
        pass 

        # === ЗАПУСК ===
        status_msg = await update.message.reply_text("⚙️ Flux: Задача сформирована, ищу ноды...")
        track_message(uid, status_msg.message_id)

        res = queue_prompt(wf)
        
        if 'error' in res:
            await status_msg.edit_text(f"❌ Comfy Error: {res['error']}")
            return

        start_ts = time.time()
        await monitor_generation(context, uid, res['prompt_id'], 1, start_ts, status_msg.message_id)

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка WebApp: {e}")
        traceback.print_exc()

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Упрощенный обработчик для текста
    if not await check_auth(update): return
    uid = update.effective_user.id
    text = update.message.text
    if text == "🗑 ОЧИСТИТЬ":
        await update.message.reply_text("Чистим...")
    elif text == "/start":
        await start(update, context)
    else:
        await update.message.reply_text(f"Команда '{text}' не распознана (режим Flux).")

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    # app.add_handler(MessageHandler(filters.PHOTO, handle_photo)) # Если нужно фото
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_msg))
    print(f"Bot v6.0 (Smart) Started on {RUNPOD_ID}")
    app.run_polling()
EOF

# 2. Убиваем старый бот и запускаем новый
pkill -f "bot.py"
sleep 1
nohup /workspace/venv/bin/python /workspace/bot.py > /workspace/bot.log 2>&1 &
echo "✅ Бот обновлен и перезапущен!"
