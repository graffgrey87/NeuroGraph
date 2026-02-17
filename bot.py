import websocket, uuid, json, urllib.request, urllib.parse, requests, random, os, time, traceback, re, sys, html, asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, InputMediaPhoto
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# ==========================================
# ⚙️ CONFIG
# ==========================================
BOT_TOKEN = os.getenv("TG_TOKEN")
raw_ids = os.getenv("ADMIN_ID", "")
ALLOWED_USERS = [int(x) for x in raw_ids.split(",") if x.strip().isdigit()] if raw_ids else []

COMFY_PORT = "3000"
RUNPOD_ID = os.environ.get("RUNPOD_POD_ID", "127.0.0.1")
COMFY_SERVER = f"127.0.0.1:{COMFY_PORT}"
BASE_DIR = "/workspace"
CLIENT_ID = str(uuid.uuid4())
WEBAPP_URL = f"https://{RUNPOD_ID}-8099.proxy.runpod.net"

# ПУТИ К ФАЙЛАМ
WORKFLOWS = {
    "edit": { "file": os.path.join(BASE_DIR, "workflow_api.json"), "name": "🎨 Редакт (Qwen)", "need_photo": True },
    "gen":  { "file": os.path.join(BASE_DIR, "workflow_gen.json"), "name": "✨ Генерация (Legacy)", "need_photo": False },
    "flux": { "file": os.path.join(BASE_DIR, "TI2I_Flux2_Klein.json"), "name": "🚀 Flux Pro", "need_photo": False }
}

# ШАБЛОНЫ ИЗ 5.3
PROMPT_NORMAL = "На фото крупным планом показана высокая девушка с изображения 1 которая __действие__ __место__. На ней __наряд__. Её наряд выполнен в __цвет__. Из украшений на ней __украшения__. Ракурс __ракурс__, __угол__, __крупность__ __выражения__. Фото в стиле __стиль__, реалистичное освещение."
PROMPT_NSFW = "На фото крупным планом показана высокая девушка с изображения 1, которая __действие_nsfw__ __место__. На ней __наряд_nsfw__. Она __доп_действие_nsfw__. Её наряд выполнен в __цвет__. Из украшений на ней __украшения__. Ракурс __ракурс__, __угол__, __крупность__ __выражения__. Фото в стиле __стиль__, реалистичное освещение."

user_data = {}

if not BOT_TOKEN: sys.exit("❌ TOKEN MISSING")

# ==========================================
# 🛠 UTILS
# ==========================================
def get_user_data(uid):
    if uid not in user_data:
        user_data[uid] = {
            'image': None, 'mode': 'normal', 'wf': 'flux', 'batch': 1, 
            'dataset_name': 'Batch', 'msg_ids': [], 
            'loras': {1:0.0, 2:0.0, 3:0.0, 4:0.0}, # Для Legacy
            'flux_store': None, # Память Flux
            'awaiting_lora': None, 'awaiting_custom_batch': False, 'awaiting_dataset_name': False
        }
    return user_data[uid]

def track_message(uid, mid):
    """Запоминает ID сообщений для очистки"""
    d = get_user_data(uid)
    if mid not in d['msg_ids']: d['msg_ids'].append(mid)
    if len(d['msg_ids']) > 200: d['msg_ids'].pop(0)

def repair_workflow(wf):
    """Базовый ремонт путей и проверка на пустоту"""
    clean_wf = {}
    for nid, node in wf.items():
        if not isinstance(node, dict): continue
        # Fix Windows Paths
        if "inputs" in node:
            for k, v in node["inputs"].items():
                if isinstance(v, str): node["inputs"][k] = v.replace("\\", "/")
        # Safety check
        if "class_type" not in node and "inputs" in node:
            node["class_type"] = "Reroute"
        clean_wf[nid] = node
    return clean_wf

def apply_flux_settings(wf, data):
    """Применяет настройки WebApp к JSON с переводом разрешений"""
    # 1. MODEL
    if "116:129" in wf:
        wf["116:129"]["inputs"]["model_name"] = data["ckpt"]
        wf["116:129"]["inputs"]["weight_dtype"] = data["dtype"]
        if "sage_attention" in wf["116:129"]["inputs"]: wf["116:129"]["inputs"]["sage_attention"] = data["sage"]
    
    if "116:120" in wf and data["clip"]: wf["116:120"]["inputs"]["clip_name"] = data["clip"]
    if "116:115" in wf and data["vae"]: wf["116:115"]["inputs"]["vae_name"] = data["vae"]

    # 2. PARAMS + RESOLUTION FIX
    RES_MAP = {
        "1024x1024 (Square)": "1:1 (Square)", "1600x900 (Landscape)": "16:9 (Landscape)",
        "900x1600 (Portrait)": "9:16 (Portrait)", "1216x832 (Landscape)": "3:2 (Landscape)",
        "832x1216 (Portrait)": "2:3 (Portrait)"
    }
    raw_res = data["res"]
    wf["101"]["inputs"]["aspect_ratio"] = RES_MAP.get(raw_res, raw_res)

    wf["117"]["inputs"]["seed"] = int(data["seed"]) if int(data["seed"]) != -1 else random.randint(1, 10**15)
    wf["119"]["inputs"]["Xi"] = int(data["steps"]); wf["119"]["inputs"]["Xf"] = int(data["steps"])
    wf["118"]["inputs"]["Xi"] = float(data["cfg"]); wf["118"]["inputs"]["Xf"] = float(data["cfg"])
    wf["161"]["inputs"]["value"] = data["pos"]
    wf["162"]["inputs"]["value"] = data["neg"]
    
    # 3. CONTROLS
    wf["146"]["inputs"]["value"] = int(data["rot"]); wf["144"]["inputs"]["value"] = int(data["ang"]) 
    wf["151"]["inputs"]["value"] = int(data["dist"])
    wf["228"]["inputs"]["Xi"] = float(data["ctx"]); wf["228"]["inputs"]["Xf"] = float(data["ctx"])
    wf["229"]["inputs"]["Xi"] = float(data["resc"]); wf["229"]["inputs"]["Xf"] = float(data["resc"])
    wf["139"]["inputs"]["Xi"] = float(data["rscale"]); wf["139"]["inputs"]["Xf"] = float(data["rscale"])

    # 4. LORAS
    if "153" in wf:
        for i in range(1,14): 
            if f"lora_{i}" in wf["153"]["inputs"]: wf["153"]["inputs"][f"lora_{i}"] = {"on": False}
        for i, l in enumerate(data["loras"]):
            wf["153"]["inputs"][f"lora_{i+1}"] = {"on": True, "lora": l["name"], "strength": l["weight"]}

    # 5. REFS
    loaders = {1:"76", 2:"104", 3:"105", 4:"182", 5:"183", 6:"184"}
    for i in range(1,7): 
        gid = 211+i
        if f"{gid}:214" in wf: wf[f"{gid}:214"]["inputs"]["value"] = False
    
    for r in data["refs"]:
        idx = r["idx"]
        gid = 211+idx
        if loaders[idx] in wf: wf[loaders[idx]]["inputs"]["image"] = r["image"]
        if f"{gid}:214" in wf: wf[f"{gid}:214"]["inputs"]["value"] = r["active"]
        if f"{gid}:213" in wf: wf[f"{gid}:213"]["inputs"]["switch"] = r["flip"]
        if f"{gid}:209" in wf: wf[f"{gid}:209"]["inputs"]["rotation"] = r["rot"]
    
    return wf

async def check_auth(update):
    if ALLOWED_USERS and update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ Private Bot")
        return False
    return True

def find_node_id(workflow, class_type_list):
    if isinstance(workflow, dict):
        for node_id, node_data in workflow.items():
            if isinstance(node_data, dict) and node_data.get("class_type") in class_type_list: 
                return node_id
    return None

def get_lora_names(uid):
    names = {1: "LORA 1", 2: "LORA 2", 3: "LORA 3", 4: "LORA 4"}
    data = get_user_data(uid)
    if data['wf'] not in WORKFLOWS: return names
    target = WORKFLOWS[data['wf']]['file']
    if not os.path.exists(target): return names
    try:
        with open(target, "r", encoding="utf-8") as f: wf = json.load(f)
        nid = find_node_id(wf, ["Power Lora Loader (rgthree)"])
        if nid:
            inputs = wf[nid]["inputs"]
            for i in range(1, 5):
                key = f"lora_{i}"
                if key in inputs and "lora" in inputs[key]:
                    raw = inputs[key]["lora"]
                    clean = raw.replace("\\", "/").split("/")[-1]
                    clean = clean.replace(".safetensors", "").replace("_", " ")
                    if len(clean) > 20: clean = clean[:18] + ".."
                    names[i] = clean
    except: pass
    return names

# --- API ---
def upload_image(file_bytes, file_name):
    try:
        files = {'image': (file_name, file_bytes)}
        data = {'type': 'input', 'overwrite': 'true'}
        return requests.post(f"http://{COMFY_SERVER}/upload/image", files=files, data=data).json()
    except: return None

def queue_prompt(wf):
    clean_wf = repair_workflow(wf)
    try:
        data = json.dumps({"prompt": clean_wf, "client_id": CLIENT_ID}).encode('utf-8')
        req = urllib.request.Request(f"http://{COMFY_SERVER}/prompt", data=data)
        return json.loads(urllib.request.urlopen(req).read())
    except Exception as e: return {'error': str(e)}

def get_history(pid):
    try:
        with urllib.request.urlopen(f"http://{COMFY_SERVER}/history/{pid}") as r: return json.loads(r.read())
    except: return {}

def get_view(filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen(f"http://{COMFY_SERVER}/view?{url_values}") as response:
        return response.read()

# --- KEYBOARDS ---
def get_main_kb(uid):
    d = get_user_data(uid)
    ico = "😇" if d['mode'] == 'normal' else "😈"
    kb = [
        [KeyboardButton("🎛 ОТКРЫТЬ ПУЛЬТ (Flux)", web_app=WebAppInfo(url=WEBAPP_URL))],
        [KeyboardButton("🚀 ГЕНЕРАЦИЯ"), KeyboardButton("🗑 ОЧИСТИТЬ")],
        [KeyboardButton(f"🔄 WF: {WORKFLOWS[d['wf']]['name']}"), KeyboardButton(f"🔢 Кол-во: {d['batch']}")],
        [KeyboardButton(f"{ico} Режим: {d['mode'].upper()}"), KeyboardButton("🎛 LORA MIXER")],
        [KeyboardButton(f"🏷 Сет: {d['dataset_name']}"), KeyboardButton("🌐 Ссылки")]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def get_lora_kb(uid):
    # Для Legacy режимов
    d = get_user_data(uid)
    real_names = get_lora_names(uid)
    kb = []
    for i in range(1, 5):
        val = d['loras'].get(i, 0.0)
        status = f"✅ {val}" if val > 0 else "❌ OFF"
        kb.append([InlineKeyboardButton(f"{i}. {real_names[i]} | {status}", callback_data=f"edit_lora_{i}")])
    kb.append([InlineKeyboardButton("🔙 Закрыть", callback_data="close_lora")])
    return InlineKeyboardMarkup(kb)

def get_links_kb():
    base = f"https://{RUNPOD_ID}"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎨 ComfyUI", url=f"{base}-{COMFY_PORT}.proxy.runpod.net/")],
        [InlineKeyboardButton("🖼 Gallery", url=f"{base}-8083.proxy.runpod.net/"), InlineKeyboardButton("🧠 CivitAI", url=f"{base}-8082.proxy.runpod.net/")],
        [InlineKeyboardButton("❌ Close", callback_data="close_links")]
    ])

def get_batch_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1", callback_data="batch_1"), InlineKeyboardButton("2", callback_data="batch_2"), InlineKeyboardButton("4", callback_data="batch_4")],
        [InlineKeyboardButton("⌨️ Custom", callback_data="batch_custom")]
    ])

# ==========================================
# 🎮 HANDLERS
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    uid = update.effective_user.id
    msg = await update.message.reply_text(f"🤖 **NeuroGraph v7.5 Final**", reply_markup=get_main_kb(uid), parse_mode="Markdown")
    track_message(uid, msg.message_id)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    uid = update.effective_user.id
    track_message(uid, update.message.message_id)
    msg = await update.message.reply_text("📥 Сохраняю...")
    track_message(uid, msg.message_id)
    try:
        f = await update.message.photo[-1].get_file()
        fname = f"user_{uid}_{int(time.time())}.jpg"
        resp = upload_image(await f.download_as_bytearray(), fname)
        if resp:
            real = resp.get("name", fname)
            get_user_data(uid)['image'] = real
            await msg.edit_text(f"✅ Фото: `{real}`", parse_mode="Markdown")
        else: await msg.edit_text("❌ Ошибка")
    except Exception as e: await msg.edit_text(f"Error: {e}")

# --- WEBAPP (FLUX + MEMORY + PREVIEW) ---
async def handle_webapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    uid = update.effective_user.id
    try:
        data = json.loads(update.effective_message.web_app_data.data)
        d = get_user_data(uid)
        d['flux_store'] = data # 💾 Запоминаем
        
        # 🖼 ПРЕВЬЮ РЕФЕРЕНСОВ
        active_refs = [r for r in data['refs'] if r['active']]
        if active_refs:
            m1 = await context.bot.send_message(uid, f"👀 **Активные референсы ({len(active_refs)}):**", parse_mode="Markdown")
            track_message(uid, m1.message_id)
            for r in active_refs:
                try:
                    img_data = get_view(r['image'], "", "input")
                    m = await context.bot.send_photo(uid, img_data, caption=f"Ref {r['idx']} (Rot: {r['rot']})")
                    track_message(uid, m.message_id)
                except: pass

        # ЗАПУСК
        with open(WORKFLOWS["flux"]["file"], "r", encoding="utf-8") as f: wf = json.load(f)
        wf = apply_flux_settings(wf, data)
        
        msg = await update.message.reply_text(f"🎬 Flux Pro: {data['res']}")
        track_message(uid, msg.message_id)
        asyncio.create_task(run_workflow(context, uid, wf, msg, 1))
        
    except Exception as e:
        m = await update.message.reply_text(f"WebApp Error: {e}")
        track_message(uid, m.message_id)
        traceback.print_exc()

# --- TEXT HANDLER ---
async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    uid = update.effective_user.id
    text = update.message.text
    d = get_user_data(uid)
    track_message(uid, update.message.message_id)

    if d.get('awaiting_custom_batch'):
        if text.isdigit():
            d['batch'] = int(text)
            d['awaiting_custom_batch'] = False
            m = await update.message.reply_text(f"🔢 Batch: {d['batch']}", reply_markup=get_main_kb(uid))
        else: m = await update.message.reply_text("Введите число")
        track_message(uid, m.message_id)
        return
    
    if d.get('awaiting_dataset_name'):
        d['dataset_name'] = text
        d['awaiting_dataset_name'] = False
        m = await update.message.reply_text(f"🏷 Set: {text}", reply_markup=get_main_kb(uid))
        track_message(uid, m.message_id)
        return

    if d['awaiting_lora']:
        try:
            val = float(text.replace(",", "."))
            d['loras'][d['awaiting_lora']] = val
            d['awaiting_lora'] = None
            m = await update.message.reply_text("🎛 Mixer:", reply_markup=get_lora_kb(uid))
        except: m = await update.message.reply_text("Число!")
        track_message(uid, m.message_id)
        return

    # COMMANDS
    if text == "🗑 ОЧИСТИТЬ":
        for mid in reversed(d['msg_ids']):
            try: await context.bot.delete_message(uid, mid)
            except: pass
        d['msg_ids'] = []
        m = await update.message.reply_text("🧹 Чат очищен", reply_markup=get_main_kb(uid))
        track_message(uid, m.message_id)

    elif text == "🚀 ГЕНЕРАЦИЯ":
        if d['wf'] == 'flux':
            # 🚀 ЗАПУСК ИЗ ПАМЯТИ
            if d['flux_store']:
                data = d['flux_store']
                m = await update.message.reply_text(f"🚀 Повтор Flux ({data['res']})...")
                track_message(uid, m.message_id)
                with open(WORKFLOWS["flux"]["file"], "r", encoding="utf-8") as f: wf = json.load(f)
                wf = apply_flux_settings(wf, data)
                asyncio.create_task(run_workflow(context, uid, wf, m, 1))
            else:
                m = await update.message.reply_text("⚠️ Сначала настрой через Пульт!")
                track_message(uid, m.message_id)
        else:
            await run_legacy_gen(update, context, uid)

    elif text == "🎛 LORA MIXER":
        m = await update.message.reply_text("🎛 Лорки (Legacy):", reply_markup=get_lora_kb(uid))
        track_message(uid, m.message_id)

    elif text == "🌐 Ссылки":
        m = await update.message.reply_text("Links:", reply_markup=get_links_kb())
        track_message(uid, m.message_id)

    elif text.startswith("🔢"):
        m = await update.message.reply_text("Кол-во:", reply_markup=get_batch_kb())
        track_message(uid, m.message_id)

    elif text.startswith("🏷"):
        d['awaiting_dataset_name'] = True
        m = await update.message.reply_text("Имя сета:")
        track_message(uid, m.message_id)

    elif text.startswith("🔄"):
        keys = list(WORKFLOWS.keys())
        d['wf'] = keys[(keys.index(d['wf']) + 1) % len(keys)]
        m = await update.message.reply_text(f"🔄 Режим: **{WORKFLOWS[d['wf']]['name']}**", reply_markup=get_main_kb(uid), parse_mode="Markdown")
        track_message(uid, m.message_id)

    elif "Режим:" in text:
        d['mode'] = 'nsfw' if d['mode'] == 'normal' else 'normal'
        m = await update.message.reply_text(f"Режим: {d['mode'].upper()}", reply_markup=get_main_kb(uid))
        track_message(uid, m.message_id)

    else:
        if d['wf'] != 'flux':
            await run_legacy_gen(update, context, uid, manual_prompt=text)

# --- EXECUTION ---
async def run_workflow(context, uid, wf, status_msg, batch_idx):
    start_time = time.time() # ⏱ СТАРТ
    try:
        res = queue_prompt(wf)
        if 'error' in res:
            await status_msg.edit_text(f"❌ Error: {res['error']}")
            return

        pid = res['prompt_id']
        while True:
            h = get_history(pid)
            if pid in h: break
            await asyncio.sleep(1)

        out = h[pid]['outputs']
        found = False
        
        # ⏱ СТОП
        duration = time.time() - start_time
        time_str = f"⏱ {duration:.1f}s"

        caption = f"✅ Result {batch_idx} | {time_str}"
        for nid, dat in out.items():
            if 'text' in dat:
                val = dat['text']
                txt = str(val[0] if isinstance(val, list) else val)[:800]
                caption += f"\n\n📝 {html.escape(txt)}"
                break

        for nid in out:
            if 'images' in out[nid]:
                for img in out[nid]['images']:
                    idata = get_view(img['filename'], img['subfolder'], img['type'])
                    m = await context.bot.send_photo(uid, idata, caption=caption, parse_mode="HTML")
                    track_message(uid, m.message_id)
                    found = True
        
        if found: await status_msg.delete()
        else: await status_msg.edit_text("⚠️ No output")
    except Exception as e: 
        await context.bot.send_message(uid, f"Runtime: {e}")

async def run_legacy_gen(update, context, uid, manual_prompt=None):
    d = get_user_data(uid)
    cfg = WORKFLOWS[d['wf']]
    
    if cfg['need_photo'] and not d['image']:
        m = await update.message.reply_text("⚠️ Нужно фото!")
        track_message(uid, m.message_id)
        return

    prompt_txt = manual_prompt if manual_prompt else (PROMPT_NORMAL if d['mode'] == 'normal' else PROMPT_NSFW)
    status = await update.message.reply_text(f"🚀 {d['batch']}x {cfg['name']}...")
    track_message(uid, status.message_id)

    for i in range(d['batch']):
        with open(cfg['file'], "r") as f: wf = json.load(f)
        
        if cfg['need_photo']:
            img_node = find_node_id(wf, ["LoadImage", "LoadImageMask"])
            if img_node: wf[img_node]["inputs"]["image"] = d['image']
        
        sid = find_node_id(wf, ["EasySeed", "Seed", "KSampler"])
        if sid and "seed" in wf[sid]["inputs"]: wf[sid]["inputs"]["seed"] = random.randint(1, 10**15)

        tid = find_node_id(wf, ["CLIPTextEncode", "PrimitiveString"])
        if tid: 
             k = "string" if "string" in wf[tid]["inputs"] else "text"
             wf[tid]["inputs"][k] = prompt_txt

        if "211" in wf and "inputs" in wf["211"]:
            wf["211"]["inputs"]["value"] = d['dataset_name']

        asyncio.create_task(run_workflow(context, uid, wf, status, i+1))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    d = get_user_data(uid)
    await q.answer()
    
    if q.data.startswith("batch_"):
        if "custom" in q.data:
            d['awaiting_custom_batch'] = True
            await q.message.edit_text("⌨️ **Введите число**:", parse_mode="Markdown")
        else:
            d['batch'] = int(q.data.split("_")[1])
            await q.message.delete()
            m = await context.bot.send_message(uid, f"🔢 Batch: **{d['batch']}**", reply_markup=get_main_kb(uid), parse_mode="Markdown")
            track_message(uid, m.message_id)
    
    elif q.data.startswith("edit_lora_"):
        slot = int(q.data.split("_")[2])
        d['awaiting_lora'] = slot
        names = get_lora_names(uid)
        await q.message.edit_text(f"✍️ **{names[slot]}**\nВес (0.1 - 1.0):", parse_mode="Markdown")

    elif q.data in ["close_links", "close_lora"]: await q.message.delete()

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_msg))
    print(f"✅ Bot v7.5 Final Started on {RUNPOD_ID}")
    app.run_polling()
