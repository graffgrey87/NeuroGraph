import websocket, uuid, json, urllib.request, urllib.parse, requests, random, os, time, traceback, re, sys
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# ==========================================
# ⚙️ НАСТРОЙКИ (v4.7 Final + Path Fixer)
# ==========================================
BOT_TOKEN = os.getenv("TG_TOKEN")
raw_ids = os.getenv("ADMIN_ID")
ALLOWED_USERS = [int(x) for x in raw_ids.split(",") if x.strip().isdigit()] if raw_ids else []

COMFY_PORT = "3000"
RUNPOD_ID = os.environ.get("RUNPOD_POD_ID", "127.0.0.1")
COMFY_SERVER = f"127.0.0.1:{COMFY_PORT}"
MODELS_PATH = "/workspace/ComfyUI/models/loras"

if not BOT_TOKEN:
    sys.exit("❌ TG_TOKEN не задан!")

PROMPT_NORMAL = "На фото крупным планом показана высокая девушка с изображения 1 которая __действие__ __место__. На ней __наряд__. Её наряд выполнен в __цвет__. Из украшений на ней __украшения__. Ракурс __ракурс__, __угол__, __крупность__ __выражения__. Фото в стиле __стиль__, реалистичное освещение."
PROMPT_NSFW = "На фото крупным планом показана высокая девушка с изображения 1, которая __действие_nsfw__ __место__. На ней __наряд_nsfw__. Она __доп_действие_nsfw__. Её наряд выполнен в __цвет__. Из украшений на ней __украшения__. Ракурс __ракурс__, __угол__, __крупность__ __выражения__. Фото в стиле __стиль__, реалистичное освещение."

WORKFLOWS = {
    "edit": {"file": "workflow_api.json", "name": "🎨 Редакт (Qwen)", "need_photo": True},
    "gen":  {"file": "workflow_gen.json",  "name": "✨ Генерация (Flux)", "need_photo": False}
}

user_data = {}

# ==========================================
# 🛠 ФУНКЦИИ ПОМОЩНИКИ
# ==========================================
async def check_auth(update: Update):
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ Доступ запрещен.")
        return False
    return True

def get_user_data(uid):
    if uid not in user_data:
        user_data[uid] = {
            'image': None, 'mode': 'normal', 'wf': 'edit', 'batch': 1, 'msg_ids': [],
            'loras': {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}, 
            'awaiting_lora': None 
        }
    return user_data[uid]

def track_message(user_id, message_id):
    data = get_user_data(user_id)
    data['msg_ids'].append(message_id)
    if len(data['msg_ids']) > 50: data['msg_ids'].pop(0)

# 🔥 ГЛАВНЫЙ ФИКСЕР ПУТЕЙ (Linux-совместимость)
def fix_workflow_paths(workflow):
    for nid, node in workflow.items():
        if "inputs" in node:
            for key, val in node["inputs"].items():
                if isinstance(val, str) and "\\" in val:
                    # Меняем обратный слеш на прямой
                    node["inputs"][key] = val.replace("\\", "/")
    return workflow

def find_node_id(workflow, class_type_list):
    if isinstance(workflow, dict):
        for node_id, node_data in workflow.items():
            if node_data.get("class_type") in class_type_list: return node_id
    return None

# --- COMFY API ---
def upload_image_to_comfy(file_bytes, file_name):
    try:
        files = {'image': (file_name, file_bytes)}
        data = {'type': 'input', 'overwrite': 'true'}
        response = requests.post(f"http://{COMFY_SERVER}/upload/image", files=files, data=data)
        return response.json()
    except: return None

def queue_prompt(prompt_workflow):
    p = {"prompt": prompt_workflow}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request(f"http://{COMFY_SERVER}/prompt", data=data)
    return json.loads(urllib.request.urlopen(req).read())

def get_history(prompt_id):
    try:
        with urllib.request.urlopen(f"http://{COMFY_SERVER}/history/{prompt_id}") as response:
            return json.loads(response.read())
    except: return {}

def get_image(filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen(f"http://{COMFY_SERVER}/view?{url_values}") as response:
        return response.read()

# --- LORA NAMES ---
def get_lora_names_from_file():
    names = {1: "LORA 1", 2: "LORA 2", 3: "LORA 3", 4: "LORA 4"}
    try:
        if os.path.exists("workflow_api.json"):
            with open("workflow_api.json", "r", encoding="utf-8") as f:
                wf = json.load(f)
            nid = find_node_id(wf, ["Power Lora Loader (rgthree)"])
            if nid:
                inputs = wf[nid]["inputs"]
                for i in range(1, 5):
                    key = f"lora_{i}"
                    if key in inputs and "lora" in inputs[key]:
                        raw = inputs[key]["lora"]
                        # Убираем пути, оставляем только имя файла
                        clean = raw.replace("\\", "/").split("/")[-1]
                        clean = clean.replace(".safetensors", "")
                        clean = clean.replace("_", " ").replace("*", "").replace("`", "")
                        if len(clean) > 20: clean = clean[:18] + ".."
                        names[i] = clean
    except: pass
    return names

# --- KEYBOARDS ---
def get_main_keyboard(uid):
    data = get_user_data(uid)
    wf_name = WORKFLOWS[data['wf']]['name']
    mode_icon = "😇" if data['mode'] == 'normal' else "😈"
    keyboard = [
        [KeyboardButton("🚀 ГЕНЕРАЦИЯ"), KeyboardButton("🗑 ОЧИСТИТЬ")],
        [KeyboardButton(f"🔄 WF: {wf_name}"), KeyboardButton(f"🔢 Кол-во: {data['batch']}")],
        [KeyboardButton(f"{mode_icon} Режим: {data['mode'].upper()}"), KeyboardButton("🎛 LORA MIXER")],
        [KeyboardButton("🌐 Ссылки & WebUI")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_lora_keyboard(uid):
    data = get_user_data(uid)
    real_names = get_lora_names_from_file()
    keyboard = []
    
    for i in range(1, 5):
        val = data['loras'].get(i, 0.0)
        status = f"✅ {val}" if val > 0 else "❌ OFF"
        name = real_names[i]
        keyboard.append([InlineKeyboardButton(f"{i}. {name} | {status}", callback_data=f"edit_lora_{i}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Закрыть меню", callback_data="close_lora")])
    return InlineKeyboardMarkup(keyboard)

def get_links_keyboard():
    base = f"https://{RUNPOD_ID}"
    url_comfy = f"{base}-{COMFY_PORT}.proxy.runpod.net/"
    url_gallery = f"{base}-8083.proxy.runpod.net/"
    url_down = f"{base}-8081.proxy.runpod.net/"
    url_civit = f"{base}-8082.proxy.runpod.net/"
    url_jupyter = f"{base}-8888.proxy.runpod.net/"
    
    keyboard = [
        [InlineKeyboardButton("🎨 ComfyUI Web", url=url_comfy)],
        [InlineKeyboardButton("🖼 Галерея (8083)", url=url_gallery), InlineKeyboardButton("💾 Downloader (8081)", url=url_down)],
        [InlineKeyboardButton("🧠 CivitAI (8082)", url=url_civit), InlineKeyboardButton("📂 Jupyter (8888)", url=url_jupyter)]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_batch_keyboard():
    keyboard = [
        [InlineKeyboardButton("1", callback_data="batch_1"), InlineKeyboardButton("2", callback_data="batch_2"), InlineKeyboardButton("3", callback_data="batch_3"), InlineKeyboardButton("5", callback_data="batch_5")],
        [InlineKeyboardButton("10", callback_data="batch_10")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    uid = update.effective_user.id
    msg = await update.message.reply_text(f"🎛 **Center v4.7**\nID: `{RUNPOD_ID}`", reply_markup=get_main_keyboard(uid), parse_mode="Markdown")
    track_message(uid, update.message.message_id)
    track_message(uid, msg.message_id)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    uid = update.effective_user.id
    track_message(uid, update.message.message_id)
    msg = await update.message.reply_text("📥 Загрузка...")
    track_message(uid, msg.message_id)
    try:
        photo = await update.message.photo[-1].get_file()
        fname = f"qwen_{uid}_{uuid.uuid4().hex[:4]}.jpg"
        fbytes = await photo.download_as_bytearray()
        resp = upload_image_to_comfy(fbytes, fname)
        if resp:
            real_name = resp.get("name", fname)
            get_user_data(uid)['image'] = real_name
            await msg.edit_text(f"✅ Фото принято: `{real_name}`", parse_mode="Markdown")
        else: await msg.edit_text("❌ Ошибка загрузки.")
    except Exception as e: await msg.edit_text(f"Ошибка: {e}")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    data = get_user_data(uid)
    await query.answer()

    if query.data.startswith("batch_"):
        count = int(query.data.split("_")[1])
        data['batch'] = count
        await query.message.edit_text(f"🔢 Установлено: **{count} шт.**", parse_mode="Markdown")
        m = await context.bot.send_message(chat_id=uid, text="Меню обновлено:", reply_markup=get_main_keyboard(uid))
        track_message(uid, m.message_id)

    elif query.data.startswith("edit_lora_"):
        slot = int(query.data.split("_")[2])
        data['awaiting_lora'] = slot
        names = get_lora_names_from_file()
        await query.message.edit_text(f"✍️ **LORA {slot}:** `{names[slot]}`\nВведите силу (например `0.8`).\nНапишите `0`, чтобы выключить.", parse_mode="Markdown")
    
    elif query.data == "close_lora":
        await query.message.delete()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    uid = update.effective_user.id
    text = update.message.text
    data = get_user_data(uid)
    track_message(uid, update.message.message_id)

    if data['awaiting_lora'] is not None:
        try:
            val = float(text.replace(",", "."))
            slot = data['awaiting_lora']
            data['loras'][slot] = val
            data['awaiting_lora'] = None
            
            names = get_lora_names_from_file()
            await update.message.reply_text(f"🔧 *{names[slot]}* -> {val}", reply_markup=get_main_keyboard(uid), parse_mode="Markdown")
            
            m = await update.message.reply_text("🎛 Микшер:", reply_markup=get_lora_keyboard(uid))
            track_message(uid, m.message_id)
            return
        except ValueError:
            await update.message.reply_text("⚠️ Нужно ввести число (например 0.5).")
            return

    if text == "🗑 ОЧИСТИТЬ":
        for mid in reversed(data['msg_ids']):
            try: await context.bot.delete_message(chat_id=uid, message_id=mid)
            except: pass
        data['msg_ids'] = []
    
    elif text == "🎛 LORA MIXER":
        m = await update.message.reply_text("🎛 **Настройка LORA:**", reply_markup=get_lora_keyboard(uid))
        track_message(uid, m.message_id)

    elif text == "🌐 Ссылки & WebUI":
        m = await update.message.reply_text("🔗 Сервисы:", reply_markup=get_links_keyboard())
        track_message(uid, m.message_id)
    
    elif text.startswith("🔢"):
        m = await update.message.reply_text("Количество копий:", reply_markup=get_batch_keyboard())
        track_message(uid, m.message_id)
    
    elif text.startswith("🔄"):
        data['wf'] = "gen" if data['wf'] == "edit" else "edit"
        m = await update.message.reply_text(f"🔄 WF: **{WORKFLOWS[data['wf']]['name']}**", reply_markup=get_main_keyboard(uid), parse_mode="Markdown")
        track_message(uid, m.message_id)
    
    elif "Режим:" in text:
        data['mode'] = 'nsfw' if data['mode'] == 'normal' else 'normal'
        m = await update.message.reply_text(f"Режим: {data['mode'].upper()}", reply_markup=get_main_keyboard(uid))
        track_message(uid, m.message_id)
    
    elif text == "🚀 ГЕНЕРАЦИЯ":
        await execute_generation(update, context, uid)
    
    else:
        await execute_generation(update, context, uid, manual_prompt=text)

async def execute_generation(update, context, uid, manual_prompt=None):
    data = get_user_data(uid)
    wf_config = WORKFLOWS[data['wf']]
    
    if wf_config['need_photo'] and not data['image']:
        m = await update.message.reply_text(f"⚠️ Для '{wf_config['name']}' нужно фото!")
        track_message(uid, m.message_id)
        return

    raw_prompt = manual_prompt if manual_prompt else (PROMPT_NORMAL if data['mode'] == 'normal' else PROMPT_NSFW)
    count = data['batch']
    
    status_msg = await update.message.reply_text(f"🚀 Серия: **{count} шт.**\nWF: {wf_config['name']}", parse_mode="Markdown")
    track_message(uid, status_msg.message_id)

    for i in range(count):
        start_time = time.time()
        try:
            if not os.path.exists(wf_config['file']):
                await context.bot.send_message(chat_id=uid, text=f"❌ Нет файла `{wf_config['file']}`!")
                break
            with open(wf_config['file'], "r", encoding="utf-8") as f: workflow = json.load(f)

            # === 🔥 ВЫЗЫВАЕМ ФИКСЕР ПУТЕЙ ===
            workflow = fix_workflow_paths(workflow)

            # === 1. LORA MIXER ===
            id_lora = find_node_id(workflow, ["Power Lora Loader (rgthree)"])
            if id_lora:
                node = workflow[id_lora]
                for slot_idx in range(1, 5):
                    key = f"lora_{slot_idx}"
                    if key in node["inputs"]:
                        user_strength = data['loras'].get(slot_idx, 0.0)
                        node["inputs"][key]["strength"] = user_strength
                        node["inputs"][key]["on"] = (user_strength > 0)

            # === 3. SEED ===
            id_seed = find_node_id(workflow, ["easy seed", "EasySeed"])
            if id_seed:
                new_seed = random.randint(1, 10**15)
                workflow[id_seed]["inputs"]["seed"] = new_seed
            else:
                id_seed = find_node_id(workflow, ["Seed", "KSampler"])
                if id_seed and "seed" in workflow[id_seed]["inputs"]:
                     workflow[id_seed]["inputs"]["seed"] = random.randint(1, 10**15)

            # === 4. SETUP ===
            id_image = find_node_id(workflow, ["LoadImage"])
            id_prompt = find_node_id(workflow, ["String Literal", "CLIPTextEncode", "PrimitiveString"])
            
            if id_image and wf_config['need_photo']: 
                workflow[id_image]["inputs"]["image"] = data['image']
            
            if id_prompt:
                target = "string" if "string" in workflow[id_prompt]["inputs"] else "text"
                workflow[id_prompt]["inputs"][target] = raw_prompt

            prompt_data = queue_prompt(workflow)
            if 'error' in prompt_data:
                await context.bot.send_message(chat_id=uid, text=f"Comfy Error: {prompt_data['error']}")
                break

            prompt_id = prompt_data["prompt_id"]
            
            while True:
                hist = get_history(prompt_id)
                if prompt_id in hist: break
                time.sleep(1)
            
            # === RESULT ===
            duration = time.time() - start_time
            hist_data = hist[prompt_id]
            found_img = False
            final_text_log = ""

            if 'outputs' in hist_data:
                for nid in hist_data['outputs']:
                    node_out = hist_data['outputs'][nid]
                    if 'text' in node_out:
                        val = node_out['text']
                        final_text_log = str(val[0]) if isinstance(val, list) else str(val)
                    
                    if 'images' in node_out:
                        for img in node_out['images']:
                            idata = get_image(img['filename'], img['subfolder'], img['type'])
                            cap = f"🖼 {i+1}/{count} | ⏱ {duration:.1f}с"
                            if final_text_log: cap += f"\n\n📝 **Промпт:**\n_{final_text_log[:800]}_"
                            m = await context.bot.send_photo(chat_id=uid, photo=idata, caption=cap, parse_mode="Markdown")
                            track_message(uid, m.message_id)
                            found_img = True

            if not found_img:
                await context.bot.send_message(chat_id=uid, text=f"⚠️ {i+1}/{count}: Пустой результат ({duration:.1f}с)")

        except Exception as e:
            await context.bot.send_message(chat_id=uid, text=f"🔥 Ошибка: {e}")
            traceback.print_exc()

    await context.bot.delete_message(chat_id=uid, message_id=status_msg.message_id)
    fin = await context.bot.send_message(chat_id=uid, text="🏁 Готово!")
    track_message(uid, fin.message_id)

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print(f"Бот v4.7 (Anti-Crash) запущен! RunPod ID: {RUNPOD_ID}")
    app.run_polling()
