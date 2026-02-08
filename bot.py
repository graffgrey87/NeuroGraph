import websocket, uuid, json, urllib.request, urllib.parse, requests, random, os, time, traceback, re, sys
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# ==========================================
# ⚙️ КОНФИГУРАЦИЯ
# ==========================================
BASE_DIR = "/workspace"
COMFY_PORT = "3000"
COMFY_SERVER = f"127.0.0.1:{COMFY_PORT}"
BOT_TOKEN = os.getenv("TG_TOKEN")
RUNPOD_ID = os.environ.get("RUNPOD_POD_ID", "127.0.0.1")

raw_ids = os.getenv("ADMIN_ID")
ALLOWED_USERS = [int(x) for x in raw_ids.split(",") if x.strip().isdigit()] if raw_ids else []

if not BOT_TOKEN:
    sys.exit("❌ TG_TOKEN не найден")

# Пути к файлам
WORKFLOWS = {
    "edit": {"file": os.path.join(BASE_DIR, "workflow_api.json"), "name": "🎨 Редакт (Qwen)", "need_photo": True},
    "gen":  {"file": os.path.join(BASE_DIR, "workflow_gen.json"),  "name": "✨ Генерация (Flux)", "need_photo": False}
}

# Шаблоны промптов
PROMPT_NORMAL = "На фото крупным планом показана высокая девушка с изображения 1 которая __действие__ __место__. На ней __наряд__. Её наряд выполнен в __цвет__. Из украшений на ней __украшения__. Ракурс __ракурс__, __угол__, __крупность__ __выражения__. Фото в стиле __стиль__, реалистичное освещение."
PROMPT_NSFW = "На фото крупным планом показана высокая девушка с изображения 1, которая __действие_nsfw__ __место__. На ней __наряд_nsfw__. Она __доп_действие_nsfw__. Её наряд выполнен в __цвет__. Из украшений на ней __украшения__. Ракурс __ракурс__, __угол__, __крупность__ __выражения__. Фото в стиле __стиль__, реалистичное освещение."

user_data = {}

# ==========================================
# 🛠 ФУНКЦИИ
# ==========================================
def get_user_data(uid):
    if uid not in user_data:
        user_data[uid] = {
            'image': None, 'mode': 'normal', 'wf': 'edit', 'batch': 1, 'msg_ids': [],
            'loras': {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}, 
            'awaiting_lora': None 
        }
    return user_data[uid]

def track_msg(uid, msg_id):
    d = get_user_data(uid)
    d['msg_ids'].append(msg_id)
    if len(d['msg_ids']) > 50: d['msg_ids'].pop(0)

# --- АГРЕССИВНЫЙ FIXER (V2) ---
def smart_fix_models(workflow):
    print("🔍 SMART FIXER V2: Запуск...")
    
    # Карта: Класс Ноды -> (Папка в models, Имя поля ввода)
    maps = {
        'VAELoader': ('vae', 'vae_name'), 
        'CLIPLoader': ('clip', 'clip_name'),
        'DualCLIPLoader': ('clip', 'clip_name1'), 
        'CheckpointLoaderSimple': ('checkpoints', 'ckpt_name'),
        'DiffusionModelLoaderKJ': ('unet', 'model_name'), # Flux часто тут
        'UNETLoader': ('unet', 'unet_name'),
        'LoraLoaderModelOnly': ('loras', 'lora_name'),
        'LoraLoader': ('loras', 'lora_name'),
        'ControlNetLoader': ('controlnet', 'control_net_name')
    }
    
    base_models = '/workspace/ComfyUI/models'

    for nid, node in workflow.items():
        if 'class_type' not in node or 'inputs' not in node: continue
        
        ctype = node['class_type']
        if ctype in maps:
            subfolder, input_key = maps[ctype]
            
            # Проверяем, есть ли такой input в ноде
            if input_key in node['inputs']:
                current_val = node['inputs'][input_key]
                target_dir = os.path.join(base_models, subfolder)
                
                # Если папка существует
                if os.path.exists(target_dir):
                    # Получаем список всех файлов
                    files = [f for f in os.listdir(target_dir) if os.path.isfile(os.path.join(target_dir, f)) and not f.startswith('.')]
                    
                    if not files:
                        print(f"⚠️ Папка пуста: {subfolder}")
                        continue
                    
                    # Если текущее значение НЕ в списке файлов -> БЕРЕМ ПЕРВЫЙ ПОПАВШИЙСЯ
                    if current_val not in files:
                        print(f"🔧 FIXER [{ctype}]: Заменяю '{current_val}' -> '{files[0]}'")
                        node['inputs'][input_key] = files[0]
                    else:
                        print(f"✅ OK [{ctype}]: Файл '{current_val}' найден.")
                else:
                     print(f"⚠️ Папка не найдена: {target_dir}")

    return workflow

def find_node_id(workflow, class_type_list):
    for node_id, node_data in workflow.items():
        if node_data.get("class_type") in class_type_list: return node_id
    return None

def get_lora_names(filepath):
    names = {1: "LORA 1", 2: "LORA 2", 3: "LORA 3", 4: "LORA 4"}
    try:
        with open(filepath, "r") as f: wf = json.load(f)
        nid = find_node_id(wf, ["Power Lora Loader (rgthree)"])
        if nid:
            inputs = wf[nid]["inputs"]
            for i in range(1, 5):
                key = f"lora_{i}"
                if key in inputs and "lora" in inputs[key]:
                    clean = inputs[key]["lora"].replace("\\", "/").split("/")[-1].replace(".safetensors", "")
                    names[i] = clean[:20]
    except: pass
    return names

# --- API ---
def upload_img(data, name):
    try:
        resp = requests.post(f"http://{COMFY_SERVER}/upload/image", files={'image': (name, data)}, data={'type': 'input', 'overwrite': 'true'})
        return resp.json()
    except: return None

def queue_prompt(wf):
    try:
        data = json.dumps({"prompt": wf}).encode('utf-8')
        req = urllib.request.Request(f"http://{COMFY_SERVER}/prompt", data=data)
        return json.loads(urllib.request.urlopen(req).read())
    except Exception as e: return {'error': str(e)}

def get_history(pid):
    try:
        with urllib.request.urlopen(f"http://{COMFY_SERVER}/history/{pid}") as r: return json.loads(r.read())
    except: return {}

def get_view(fname, sub, type):
    q = urllib.parse.urlencode({"filename": fname, "subfolder": sub, "type": type})
    with urllib.request.urlopen(f"http://{COMFY_SERVER}/view?{q}") as r: return r.read()

# --- KB ---
def get_main_kb(uid):
    d = get_user_data(uid)
    kb = [[KeyboardButton("🚀 ГЕНЕРАЦИЯ"), KeyboardButton("🗑 ОЧИСТИТЬ")],
          [KeyboardButton(f"🔄 WF: {WORKFLOWS[d['wf']]['name']}"), KeyboardButton(f"🔢 Кол-во: {d['batch']}")],
          [KeyboardButton(f"Режим: {d['mode'].upper()}"), KeyboardButton("🎛 LORA MIXER")]]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def get_lora_kb(uid):
    d = get_user_data(uid)
    wf_path = WORKFLOWS[d['wf']]['file']
    names = get_lora_names(wf_path)
    kb = []
    for i in range(1, 5):
        val = d['loras'].get(i, 0.0)
        st = f"✅ {val}" if val > 0 else "❌ OFF"
        kb.append([InlineKeyboardButton(f"{i}. {names[i]} | {st}", callback_data=f"edit_lora_{i}")])
    kb.append([InlineKeyboardButton("🔙 Назад", callback_data="close_lora")])
    return InlineKeyboardMarkup(kb)

# --- HANDLERS ---
async def start(update, context):
    uid = update.effective_user.id
    if uid not in ALLOWED_USERS: return
    msg = await update.message.reply_text(f"🎛 **NeuroGraph v4.7** (Port {COMFY_PORT})", reply_markup=get_main_kb(uid), parse_mode="Markdown")
    track_msg(uid, update.message.message_id)
    track_msg(uid, msg.message_id)

async def handle_photo(update, context):
    uid = update.effective_user.id
    if uid not in ALLOWED_USERS: return
    track_msg(uid, update.message.message_id)
    msg = await update.message.reply_text("📥...")
    try:
        f = await update.message.photo[-1].get_file()
        fname = f"img_{uid}.jpg"
        b = await f.download_as_bytearray()
        if upload_img(b, fname):
            get_user_data(uid)['image'] = fname
            await msg.edit_text("✅ Фото принято")
        else: await msg.edit_text("❌ Ошибка ComfyUI")
    except Exception as e: await msg.edit_text(f"Err: {e}")

async def handle_callback(update, context):
    q = update.callback_query
    uid = q.from_user.id
    d = get_user_data(uid)
    await q.answer()
    if q.data.startswith("edit_lora_"):
        d['awaiting_lora'] = int(q.data.split("_")[2])
        await q.message.edit_text(f"✍️ Введи вес (0.0 - 1.0):")
    elif q.data == "close_lora":
        await q.message.delete()

async def handle_msg(update, context):
    uid = update.effective_user.id
    if uid not in ALLOWED_USERS: return
    text = update.message.text
    d = get_user_data(uid)
    track_msg(uid, update.message.message_id)

    if d['awaiting_lora']:
        try:
            d['loras'][d['awaiting_lora']] = float(text.replace(",", "."))
            d['awaiting_lora'] = None
            m = await update.message.reply_text("✅ Сохранено", reply_markup=get_main_kb(uid))
            track_msg(uid, m.message_id)
            return
        except: pass

    if text == "🗑 ОЧИСТИТЬ":
        for mid in reversed(d['msg_ids']):
            try: await context.bot.delete_message(uid, mid)
            except: pass
        d['msg_ids'] = []
        m = await update.message.reply_text("🧹")
        track_msg(uid, m.message_id)

    elif text == "🎛 LORA MIXER":
        m = await update.message.reply_text("🎛 Настройка:", reply_markup=get_lora_kb(uid))
        track_msg(uid, m.message_id)

    elif text.isdigit():
        d['batch'] = int(text)
        m = await update.message.reply_text(f"🔢 Батч: {text}")
        track_msg(uid, m.message_id)

    elif text == "🚀 ГЕНЕРАЦИЯ":
        await run_generation(update, context, uid)

    elif text.startswith("🔄"):
        d['wf'] = "gen" if d['wf'] == "edit" else "edit"
        m = await update.message.reply_text(f"Режим: {WORKFLOWS[d['wf']]['name']}", reply_markup=get_main_kb(uid))
        track_msg(uid, m.message_id)
    
    elif "Режим:" in text:
        d['mode'] = 'nsfw' if d['mode'] == 'normal' else 'normal'
        m = await update.message.reply_text(f"Режим: {d['mode'].upper()}", reply_markup=get_main_kb(uid))
        track_msg(uid, m.message_id)

    else:
        await run_generation(update, context, uid, manual_prompt=text)

async def run_generation(update, context, uid, manual_prompt=None):
    d = get_user_data(uid)
    cfg = WORKFLOWS[d['wf']]
    
    if not os.path.exists(cfg['file']):
        await context.bot.send_message(uid, f"❌ Нет файла: {cfg['file']}")
        return
    if cfg['need_photo'] and not d['image']:
        m = await update.message.reply_text("⚠️ Нужно фото!")
        track_msg(uid, m.message_id)
        return

    m = await update.message.reply_text(f"🚀 {d['batch']} шт...")
    track_msg(uid, m.message_id)

    prompt_txt = manual_prompt if manual_prompt else (PROMPT_NORMAL if d['mode'] == 'normal' else PROMPT_NSFW)

    for i in range(d['batch']):
        try:
            with open(cfg['file'], "r") as f: wf = json.load(f)
            
            # 1. FIX MODEL PATHS (Агрессивный)
            wf = smart_fix_models(wf)

            # 2. LORA
            lid = find_node_id(wf, ["Power Lora Loader (rgthree)"])
            if lid:
                for s in range(1, 5):
                    k = f"lora_{s}"
                    if k in wf[lid]["inputs"]:
                        v = d['loras'][s]
                        wf[lid]["inputs"][k]["strength"] = v
                        wf[lid]["inputs"][k]["on"] = (v > 0)

            # 3. SEED
            sid = find_node_id(wf, ["easy seed", "EasySeed"])
            if sid: wf[sid]["inputs"]["seed"] = random.randint(1, 10**15)
            else:
                sid = find_node_id(wf, ["Seed", "KSampler"])
                if sid: wf[sid]["inputs"]["seed"] = random.randint(1, 10**15)

            # 4. PHOTO & TEXT
            iid = find_node_id(wf, ["LoadImage"])
            tid = find_node_id(wf, ["String Literal", "CLIPTextEncode", "PrimitiveString"])
            
            if iid and cfg['need_photo']: wf[iid]["inputs"]["image"] = d['image']
            if tid:
                tkey = "string" if "string" in wf[tid]["inputs"] else "text"
                wf[tid]["inputs"][tkey] = prompt_txt

            res = queue_prompt(wf)
            if 'error' in res:
                await context.bot.send_message(uid, f"Comfy Err: {res['error']}")
                break
            
            pid = res['prompt_id']
            while True:
                h = get_history(pid)
                if pid in h: break
                time.sleep(1)
            
            out = h[pid]['outputs']
            found = False
            for nid in out:
                if 'images' in out[nid]:
                    for img in out[nid]['images']:
                        idata = get_view(img['filename'], img['subfolder'], img['type'])
                        cap = f"📝 {prompt_txt[:20]}..." if manual_prompt else "🎲 Auto Prompt"
                        s = await context.bot.send_photo(uid, idata, caption=cap)
                        track_msg(uid, s.message_id)
                        found = True
            
            if not found:
                await context.bot.send_message(uid, "⚠️ Генерация завершена, но фото нет.")

        except Exception as e:
            await context.bot.send_message(uid, f"Crash: {e}")
            traceback.print_exc()

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_msg))
    print(f"Bot v4.7 Started on {RUNPOD_ID}")
    app.run_polling()
