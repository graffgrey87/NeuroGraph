import websocket, uuid, json, urllib.request, urllib.parse, requests, random, os, time, traceback, re, sys, html
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# ==========================================
# ⚙️ НАСТРОЙКИ (v5.2 HTML Fix)
# ==========================================
BOT_TOKEN = os.getenv("TG_TOKEN")
raw_ids = os.getenv("ADMIN_ID")
ALLOWED_USERS = [int(x) for x in raw_ids.split(",") if x.strip().isdigit()] if raw_ids else []

COMFY_PORT = "3000"
RUNPOD_ID = os.environ.get("RUNPOD_POD_ID", "127.0.0.1")
COMFY_SERVER = f"127.0.0.1:{COMFY_PORT}"
BASE_DIR = "/workspace"
CLIENT_ID = str(uuid.uuid4())

# Настройки режимов
WORKFLOWS = {
    "edit": {
        "file": os.path.join(BASE_DIR, "workflow_api.json"), 
        "name": "🎨 Редакт (Qwen)", 
        "need_photo": True
    },
    "gen": {
        "file": os.path.join(BASE_DIR, "workflow_gen.json"),  
        "name": "✨ Генерация (Flux)", 
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
# 🛠 ПОМОЩНИКИ
# ==========================================
def escape_html(text):
    """Экранирует символы для HTML (надежнее чем Markdown)"""
    return html.escape(str(text))

async def check_auth(update: Update):
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ Доступ запрещен.")
        return False
    return True

def get_user_data(uid):
    if uid not in user_data:
        user_data[uid] = {
            'image': None, 
            'mode': 'normal', 
            'wf': 'edit', 
            'batch': 1, 
            'dataset_name': 'Batch', 
            'msg_ids': [],
            'loras': {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}, 
            'awaiting_lora': None,
            'awaiting_custom_batch': False,
            'awaiting_dataset_name': False
        }
    return user_data[uid]

def track_message(user_id, message_id):
    """Сохраняет ID для очистки"""
    data = get_user_data(user_id)
    if message_id not in data['msg_ids']:
        data['msg_ids'].append(message_id)
    if len(data['msg_ids']) > 100: 
        data['msg_ids'].pop(0)

def fix_paths_for_linux(workflow):
    """Меняет \ на / (Linux Fix)"""
    for nid, node in workflow.items():
        if "inputs" in node:
            for key, val in node["inputs"].items():
                if isinstance(val, str) and "\\" in val:
                    node["inputs"][key] = val.replace("\\", "/")
    return workflow

def find_node_id(workflow, class_type_list):
    if isinstance(workflow, dict):
        for node_id, node_data in workflow.items():
            if node_data.get("class_type") in class_type_list: return node_id
    return None

# --- 🔥 ПАРСЕР ИМЕН ЛОР ---
def get_lora_names(uid):
    names = {1: "LORA 1", 2: "LORA 2", 3: "LORA 3", 4: "LORA 4"}
    data = get_user_data(uid)
    current_mode = data['wf']
    
    if current_mode not in WORKFLOWS: return names
    target_file = WORKFLOWS[current_mode]['file']
    
    if not os.path.exists(target_file): return names

    try:
        with open(target_file, "r", encoding="utf-8") as f:
            wf = json.load(f)
        
        nid = find_node_id(wf, ["Power Lora Loader (rgthree)"])
        if nid:
            inputs = wf[nid]["inputs"]
            for i in range(1, 5):
                key = f"lora_{i}"
                if key in inputs and "lora" in inputs[key]:
                    raw = inputs[key]["lora"]
                    clean = raw.replace("\\", "/").split("/")[-1]
                    clean = clean.replace(".safetensors", "")
                    clean = clean.replace("_", " ").replace("-", " ")
                    if len(clean) > 20: clean = clean[:18] + ".."
                    names[i] = clean
    except Exception as e:
        print(f"❌ Ошибка имен: {e}")
        
    return names

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

# --- КЛАВИАТУРЫ ---
def get_main_kb(uid):
    d = get_user_data(uid)
    wf_name = WORKFLOWS[d['wf']]['name']
    mode_icon = "😇" if d['mode'] == 'normal' else "😈"
    kb = [
        [KeyboardButton("🚀 ГЕНЕРАЦИЯ"), KeyboardButton("🗑 ОЧИСТИТЬ")],
        [KeyboardButton(f"🔄 WF: {wf_name}"), KeyboardButton(f"🔢 Кол-во: {d['batch']}")],
        [KeyboardButton(f"{mode_icon} Режим: {d['mode'].upper()}"), KeyboardButton("🎛 LORA MIXER")],
        [KeyboardButton(f"🏷 Имя сета: {d['dataset_name']}"), KeyboardButton("🌐 Ссылки & WebUI")]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def get_lora_kb(uid):
    d = get_user_data(uid)
    real_names = get_lora_names(uid)
    kb = []
    for i in range(1, 5):
        val = d['loras'].get(i, 0.0)
        status = f"✅ {val}" if val > 0 else "❌ OFF"
        name = real_names[i]
        kb.append([InlineKeyboardButton(f"{i}. {name} | {status}", callback_data=f"edit_lora_{i}")])
    kb.append([InlineKeyboardButton("🔙 Закрыть меню", callback_data="close_lora")])
    return InlineKeyboardMarkup(kb)

def get_links_kb():
    base = f"https://{RUNPOD_ID}"
    url_comfy = f"{base}-{COMFY_PORT}.proxy.runpod.net/"
    url_gallery = f"{base}-8083.proxy.runpod.net/"
    url_down = f"{base}-8081.proxy.runpod.net/"
    url_civit = f"{base}-8082.proxy.runpod.net/"
    url_jupyter = f"{base}-8888.proxy.runpod.net/"
    
    kb = [
        [InlineKeyboardButton("🎨 ComfyUI Web (3000)", url=url_comfy)],
        [InlineKeyboardButton("🖼 Галерея (8083)", url=url_gallery), InlineKeyboardButton("💾 Files (8081)", url=url_down)],
        [InlineKeyboardButton("🧠 CivitAI (8082)", url=url_civit), InlineKeyboardButton("📂 Jupyter (8888)", url=url_jupyter)],
        [InlineKeyboardButton("❌ Закрыть", callback_data="close_links")]
    ]
    return InlineKeyboardMarkup(kb)

def get_batch_kb():
    kb = [
        [InlineKeyboardButton("1", callback_data="batch_1"), InlineKeyboardButton("2", callback_data="batch_2"), InlineKeyboardButton("3", callback_data="batch_3")],
        [InlineKeyboardButton("5", callback_data="batch_5"), InlineKeyboardButton("10", callback_data="batch_10")],
        [InlineKeyboardButton("⌨️ Свое число", callback_data="batch_custom")]
    ]
    return InlineKeyboardMarkup(kb)

# --- ОБРАБОТЧИКИ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    uid = update.effective_user.id
    msg = await update.message.reply_text(f"🎛 **NeuroGraph v5.2**\nID: `{RUNPOD_ID}`", reply_markup=get_main_kb(uid), parse_mode="Markdown")
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
        fname = f"user_{uid}_{uuid.uuid4().hex[:4]}.jpg"
        fbytes = await photo.download_as_bytearray()
        resp = upload_image(fbytes, fname)
        if resp:
            real_name = resp.get("name", fname)
            get_user_data(uid)['image'] = real_name
            await msg.edit_text(f"✅ Фото принято: `{real_name}`", parse_mode="Markdown")
        else: await msg.edit_text("❌ Ошибка загрузки.")
    except Exception as e: await msg.edit_text(f"Ошибка: {e}")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    d = get_user_data(uid)
    await query.answer()

    if query.data.startswith("batch_"):
        if query.data == "batch_custom":
            d['awaiting_custom_batch'] = True
            await query.message.edit_text("⌨️ **Введите число** (например 50):", parse_mode="Markdown")
        else:
            count = int(query.data.split("_")[1])
            d['batch'] = count
            await query.message.edit_text(f"🔢 Batch: **{count}**", parse_mode="Markdown")
            m = await context.bot.send_message(chat_id=uid, text="Меню обновлено", reply_markup=get_main_kb(uid))
            track_message(uid, m.message_id)

    elif query.data.startswith("edit_lora_"):
        slot = int(query.data.split("_")[2])
        d['awaiting_lora'] = slot
        names = get_lora_names(uid)
        await query.message.edit_text(f"✍️ **{names[slot]}**\nВведите вес (0.1 - 1.0) или 0:", parse_mode="Markdown")
    
    elif query.data == "close_lora" or query.data == "close_links":
        await query.message.delete()

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    uid = update.effective_user.id
    text = update.message.text
    d = get_user_data(uid)
    track_message(uid, update.message.message_id)

    # 1. ВВОД СВОЕГО ЧИСЛА (BATCH)
    if d.get('awaiting_custom_batch'):
        if text.isdigit():
            val = int(text)
            d['batch'] = val
            d['awaiting_custom_batch'] = False
            m = await update.message.reply_text(f"🔢 Установлен Batch: **{val}**", reply_markup=get_main_kb(uid), parse_mode="Markdown")
            track_message(uid, m.message_id)
        else:
            m = await update.message.reply_text("⚠️ Введите целое число!")
            track_message(uid, m.message_id)
        return

    # 2. ВВОД ИМЕНИ ДАТАСЕТА (NODE 211)
    if d.get('awaiting_dataset_name'):
        d['dataset_name'] = text
        d['awaiting_dataset_name'] = False
        m = await update.message.reply_text(f"🏷 Имя сета: **{text}**", reply_markup=get_main_kb(uid), parse_mode="Markdown")
        track_message(uid, m.message_id)
        return

    # 3. ВВОД ВЕСА ЛОРЫ
    if d['awaiting_lora']:
        try:
            val = float(text.replace(",", "."))
            slot = d['awaiting_lora']
            d['loras'][slot] = val
            d['awaiting_lora'] = None
            names = get_lora_names(uid)
            m1 = await update.message.reply_text(f"✅ {names[slot]} -> {val}", reply_markup=get_main_kb(uid))
            track_message(uid, m1.message_id)
            m2 = await update.message.reply_text("🎛 Микшер:", reply_markup=get_lora_kb(uid))
            track_message(uid, m2.message_id)
            return
        except:
            m = await update.message.reply_text("⚠️ Введите число")
            track_message(uid, m.message_id)
            return

    # 4. ОЧИСТКА
    if text == "🗑 ОЧИСТИТЬ":
        count = 0
        for mid in reversed(d['msg_ids']):
            try: 
                await context.bot.delete_message(chat_id=uid, message_id=mid)
                count += 1
            except: pass
        d['msg_ids'] = []
        clean_msg = await update.message.reply_text(f"🧹 Чисто ({count} удалено).", reply_markup=get_main_kb(uid))
        track_message(uid, clean_msg.message_id)

    # 5. МЕНЮ И КОМАНДЫ
    elif text == "🎛 LORA MIXER":
        m = await update.message.reply_text("🎛 Настройка Лор:", reply_markup=get_lora_kb(uid))
        track_message(uid, m.message_id)

    elif text == "🌐 Ссылки & WebUI":
        m = await update.message.reply_text("🔗 Порты:", reply_markup=get_links_kb())
        track_message(uid, m.message_id)
    
    elif text.startswith("🔢"):
        m = await update.message.reply_text("Количество:", reply_markup=get_batch_kb())
        track_message(uid, m.message_id)
    
    elif text.startswith("🏷"):
        d['awaiting_dataset_name'] = True
        m = await update.message.reply_text("📝 Введите новое имя для файлов (префикс):")
        track_message(uid, m.message_id)
    
    elif text.startswith("🔄"):
        keys = list(WORKFLOWS.keys())
        idx = keys.index(d['wf'])
        d['wf'] = keys[(idx + 1) % len(keys)]
        m = await update.message.reply_text(f"🔄 Режим: **{WORKFLOWS[d['wf']]['name']}**", reply_markup=get_main_kb(uid), parse_mode="Markdown")
        track_message(uid, m.message_id)
    
    elif "Режим:" in text:
        d['mode'] = 'nsfw' if d['mode'] == 'normal' else 'normal'
        m = await update.message.reply_text(f"Режим: {d['mode'].upper()}", reply_markup=get_main_kb(uid))
        track_message(uid, m.message_id)
    
    elif text == "🚀 ГЕНЕРАЦИЯ":
        await run_generation(update, context, uid)
    
    else:
        await run_generation(update, context, uid, manual_prompt=text)

async def run_generation(update, context, uid, manual_prompt=None):
    d = get_user_data(uid)
    cfg = WORKFLOWS[d['wf']]
    
    if cfg['need_photo'] and not d['image']:
        m = await update.message.reply_text(f"⚠️ Нужно фото!")
        track_message(uid, m.message_id)
        return

    prompt_txt = manual_prompt if manual_prompt else (PROMPT_NORMAL if d['mode'] == 'normal' else PROMPT_NSFW)
    
    status_msg = await update.message.reply_text(f"🚀 Запуск {d['batch']} шт...\n📂 Set: {d['dataset_name']}")
    track_message(uid, status_msg.message_id)

    for i in range(d['batch']):
        start_ts = time.time()
        try:
            if not os.path.exists(cfg['file']):
                await context.bot.send_message(uid, f"❌ Нет файла: {cfg['file']}")
                break
            
            with open(cfg['file'], "r", encoding="utf-8") as f: wf = json.load(f)

            # === AUTO-FIX ===
            wf = fix_paths_for_linux(wf)

            # === SET NAME (Node 211) ===
            if "211" in wf and "inputs" in wf["211"]:
                wf["211"]["inputs"]["value"] = d['dataset_name']

            # === LORA MIXER ===
            lid = find_node_id(wf, ["Power Lora Loader (rgthree)"])
            if lid:
                for s in range(1, 5):
                    k = f"lora_{s}"
                    if k in wf[lid]["inputs"]:
                        v = d['loras'].get(s, 0.0)
                        wf[lid]["inputs"][k]["strength"] = v
                        wf[lid]["inputs"][k]["on"] = (v > 0)

            # === SEED ===
            sid = find_node_id(wf, ["easy seed", "EasySeed"])
            if sid: wf[sid]["inputs"]["seed"] = random.randint(1, 10**15)
            else:
                sid = find_node_id(wf, ["Seed", "KSampler"])
                if sid: wf[sid]["inputs"]["seed"] = random.randint(1, 10**15)

            # === PROMPT & IMAGE ===
            iid = find_node_id(wf, ["LoadImage"])
            tid = find_node_id(wf, ["String Literal", "CLIPTextEncode", "PrimitiveString"])
            
            if iid and cfg['need_photo']: wf[iid]["inputs"]["image"] = d['image']
            if tid:
                tkey = "string" if "string" in wf[tid]["inputs"] else "text"
                wf[tid]["inputs"][tkey] = prompt_txt

            res = queue_prompt(wf)
            if 'error' in res:
                await context.bot.send_message(uid, f"Comfy Error: {res['error']}")
                break
            
            pid = res['prompt_id']
            while True:
                h = get_history(pid)
                if pid in h: break
                time.sleep(1)
            
            dur = time.time() - start_ts
            out = h[pid]['outputs']
            found = False
            
            for nid in out:
                if 'images' in out[nid]:
                    for img in out[nid]['images']:
                        idata = get_view(img['filename'], img['subfolder'], img['type'])
                        
                        # 🔥 SPOILER PROMPT HTML FIX
                        safe_prompt = escape_html(prompt_txt[:900])
                        cap = f"🖼 {i+1}/{d['batch']} ({dur:.1f}s)\n\n<span class='tg-spoiler'>{safe_prompt}</span>"
                        
                        m = await context.bot.send_photo(uid, idata, caption=cap, parse_mode="HTML")
                        track_message(uid, m.message_id)
                        found = True
            
            if not found:
                m = await context.bot.send_message(uid, "⚠️ Пусто")
                track_message(uid, m.message_id)

        except Exception as e:
            m = await context.bot.send_message(uid, f"Crash: {e}")
            track_message(uid, m.message_id)
            traceback.print_exc()

    try: await context.bot.delete_message(uid, status_msg.message_id)
    except: pass
    
    fin = await context.bot.send_message(uid, "🏁 Готово!")
    track_message(uid, fin.message_id)

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_msg))
    print(f"Bot v5.2 (HTML Fix) Started on {RUNPOD_ID}")
    app.run_polling()
