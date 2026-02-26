import websockets, uuid, json, urllib.request, urllib.parse, requests, random, os, time, traceback, re, sys, html, asyncio, base64, logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, InputMediaPhoto
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from fast_downloader import (
    load_presets, save_presets, add_preset as fd_add_preset,
    get_categories_with_counts, get_presets_by_category, get_preset_info,
    download_preset, download_url as fd_download_url, download_file,
    download_cancel_flags,
    get_components, get_component, build_preset as fd_build_preset
)

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

# ПУТИ
WORKFLOWS = {
    "edit": { "file": os.path.join(BASE_DIR, "workflow_api.json"), "name": "🎨 Редакт (Qwen)", "need_photo": True },
    "gen":  { "file": os.path.join(BASE_DIR, "workflow_gen.json"), "name": "✨ Генерация (Legacy)", "need_photo": False },
    "flux": { "file": os.path.join(BASE_DIR, "TI2I_Flux2_Klein.json"), "name": "🚀 Flux Pro", "need_photo": False }
}

PROMPT_NORMAL = "На фото крупным планом показана высокая девушка с изображения 1 которая __действие__ __место__. На ней __наряд__. Её наряд выполнен в __цвет__. Из украшений на ней __украшения__. Ракурс __ракурс__, __угол__, __крупность__ __выражения__. Фото в стиле __стиль__, реалистичное освещение."
PROMPT_NSFW = "На фото крупным планом показана высокая девушка с изображения 1, которая __действие_nsfw__ __место__. На ней __наряд_nsfw__. Она __доп_действие_nsfw__. Её наряд выполнен в __цвет__. Из украшений на ней __украшения__. Ракурс __ракурс__, __угол__, __крупность__ __выражения__. Фото в стиле __стиль__, реалистичное освещение."

LORA_DIR_ROOT = os.path.join(BASE_DIR, "ComfyUI/models/loras")
LORA_DIR_QWEN = os.path.join(LORA_DIR_ROOT, "qwen")
USER_DATA_FILE = os.path.join(BASE_DIR, "user_data.json")
GEN_TIMEOUT = 300

user_data = {}

def load_user_data():
    global user_data
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, "r") as f:
                raw = json.load(f)
            user_data = {int(k): v for k, v in raw.items()}
            for uid in user_data:
                user_data[uid].setdefault('msg_ids', [])
                user_data[uid].setdefault('history', [])
                user_data[uid].setdefault('presets', {})
                user_data[uid].setdefault('awaiting_lora', None)
                user_data[uid].setdefault('awaiting_custom_batch', False)
                user_data[uid].setdefault('awaiting_dataset_name', False)
                user_data[uid].setdefault('build_state', None)
                if 'loras' in user_data[uid] and isinstance(user_data[uid]['loras'], dict):
                    user_data[uid]['loras'] = {int(k): v for k, v in user_data[uid]['loras'].items()}
            print(f"💾 Loaded {len(user_data)} user(s) from disk")
        except Exception as e:
            print(f"⚠️ Failed to load user_data: {e}")
            user_data = {}

def save_user_data():
    try:
        saveable = {}
        for uid, d in user_data.items():
            saveable[str(uid)] = {k: v for k, v in d.items() if k != 'msg_ids'}
        with open(USER_DATA_FILE, "w") as f:
            json.dump(saveable, f, ensure_ascii=False, separators=(',', ':'))
    except Exception as e:
        print(f"⚠️ Failed to save user_data: {e}")

load_user_data()

if not BOT_TOKEN: sys.exit("❌ TOKEN MISSING")

# ==========================================
# 🛠 UTILS
# ==========================================
cancel_flags = {}

def check_comfy_health():
    try:
        req = urllib.request.Request(f"http://{COMFY_SERVER}/system_stats")
        with urllib.request.urlopen(req, timeout=5) as r:
            r.read()
        return True, ""
    except Exception as e:
        return False, f"⚠️ ComfyUI недоступен: {e}"

def get_user_data(uid):
    if uid not in user_data:
        user_data[uid] = {
            'image': None, 'mode': 'normal', 'wf': 'flux', 'batch': 1, 
            'dataset_name': 'Batch', 'msg_ids': [], 'history': [], 'presets': {},
            'loras': {1:0.0, 2:0.0, 3:0.0, 4:0.0}, 
            'flux_store': None,
            'awaiting_lora': None, 'awaiting_custom_batch': False, 'awaiting_dataset_name': False,
            'build_state': None
        }
    return user_data[uid]

def track_message(uid, mid):
    d = get_user_data(uid)
    if mid not in d['msg_ids']: d['msg_ids'].append(mid)
    # Увеличили память до 500 сообщений для надежной очистки
    if len(d['msg_ids']) > 500: d['msg_ids'].pop(0)

def repair_workflow(wf):
    clean_wf = {}
    for nid, node in wf.items():
        if not isinstance(node, dict): continue
        if "inputs" in node:
            for k, v in node["inputs"].items():
                if isinstance(v, str): node["inputs"][k] = v.replace("\\", "/")
        clean_wf[nid] = node
    return clean_wf

def apply_flux_settings(wf, data, dataset_name="Batch", batch_idx=1):
    # 1. MODEL
    if "116:129" in wf:
        wf["116:129"]["inputs"]["model_name"] = data["ckpt"]
        wf["116:129"]["inputs"]["weight_dtype"] = data["dtype"]
        if "sage_attention" in wf["116:129"]["inputs"]: wf["116:129"]["inputs"]["sage_attention"] = data["sage"]
    
    if "116:120" in wf and data["clip"]: wf["116:120"]["inputs"]["clip_name"] = data["clip"]
    if "116:115" in wf and data["vae"]: wf["116:115"]["inputs"]["vae_name"] = data["vae"]

    # 2. PARAMS + FIX RES
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
    
    # 3. CONTROLS (mxSlider: Xi/Xf, не value)
    wf["146"]["inputs"]["Xi"] = int(data["rot"]); wf["146"]["inputs"]["Xf"] = int(data["rot"])
    wf["144"]["inputs"]["Xi"] = int(data["ang"]); wf["144"]["inputs"]["Xf"] = int(data["ang"])
    wf["151"]["inputs"]["Xi"] = int(data["dist"]); wf["151"]["inputs"]["Xf"] = int(data["dist"])
    wf["228"]["inputs"]["Xi"] = float(data["ctx"]); wf["228"]["inputs"]["Xf"] = float(data["ctx"])
    wf["229"]["inputs"]["Xi"] = float(data["resc"]); wf["229"]["inputs"]["Xf"] = float(data["resc"])
    wf["139"]["inputs"]["Xi"] = float(data["rscale"]); wf["139"]["inputs"]["Xf"] = float(data["rscale"])

    if "153" in wf:
        for i in range(1,14): 
            if f"lora_{i}" in wf["153"]["inputs"]: wf["153"]["inputs"][f"lora_{i}"] = {"on": False}
        for i, l in enumerate(data["loras"]):
            wf["153"]["inputs"][f"lora_{i+1}"] = {"on": True, "lora": l["name"], "strength": l["weight"]}

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

    # 5. DATASET NAMING (SaveImage node 9)
    if "9" in wf and "inputs" in wf["9"]:
        wf["9"]["inputs"]["filename_prefix"] = f"{dataset_name}/{dataset_name}_{batch_idx:03d}"

    return wf

async def check_auth(update):
    if ALLOWED_USERS and update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ Private Bot")
        return False
    return True

def get_available_loras():
    target_dir = LORA_DIR_QWEN if os.path.exists(LORA_DIR_QWEN) else LORA_DIR_ROOT
    if not os.path.exists(target_dir): return []
    files = [f for f in os.listdir(target_dir) if f.endswith(".safetensors")]
    return sorted(files)

def find_node_id(workflow, class_type_list):
    if isinstance(workflow, dict):
        for node_id, node_data in workflow.items():
            if isinstance(node_data, dict) and node_data.get("class_type") in class_type_list: 
                return node_id
    return None

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
    
    # 💡 ФОРМИРОВАНИЕ ССЫЛКИ С ПАМЯТЬЮ
    final_url = WEBAPP_URL
    try:
        init_data = dict(d['flux_store']) if d['flux_store'] else {}
        init_data['_uid'] = str(uid)
        json_str = json.dumps(init_data, separators=(',', ':'))
        b64_str = base64.urlsafe_b64encode(json_str.encode('utf-8')).decode('utf-8').rstrip("=")
        final_url = f"{WEBAPP_URL}?init={b64_str}"
    except: pass

    kb = [
        [KeyboardButton("🎛 ОТКРЫТЬ ПУЛЬТ (Flux)", web_app=WebAppInfo(url=final_url))],
        [KeyboardButton("🚀 ГЕНЕРАЦИЯ"), KeyboardButton("🗑 ОЧИСТИТЬ")],
        [KeyboardButton(f"🔄 WF: {WORKFLOWS[d['wf']]['name']}"), KeyboardButton(f"🔢 Кол-во: {d['batch']}")],
        [KeyboardButton(f"{ico} Режим: {d['mode'].upper()}"), KeyboardButton("🎛 LORA MIXER")],
        [KeyboardButton(f"🏷 Сет: {d['dataset_name']}"), KeyboardButton("📁 История"), KeyboardButton("🌐 Ссылки")],
        [KeyboardButton("📥 Загрузчик")]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def get_lora_kb(uid):
    d = get_user_data(uid)
    files = get_available_loras()
    kb = []
    for i in range(1, 5):
        idx = i - 1
        name = files[idx] if idx < len(files) else f"Slot {i} (Empty)"
        short_name = name.replace(".safetensors", "")[:18]
        val = d['loras'].get(i, 0.0)
        status = f"✅ {val}" if val > 0 else "❌ OFF"
        kb.append([InlineKeyboardButton(f"{i}. {short_name} | {status}", callback_data=f"edit_lora_{i}")])
    kb.append([InlineKeyboardButton("🔙 Закрыть", callback_data="close_lora")])
    return InlineKeyboardMarkup(kb)

def get_links_kb():
    base = f"https://{RUNPOD_ID}"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎨 ComfyUI", url=f"{base}-{COMFY_PORT}.proxy.runpod.net/")],
        [InlineKeyboardButton("� Files", url=f"{base}-8081.proxy.runpod.net/"), InlineKeyboardButton("�🖼 Gallery", url=f"{base}-8083.proxy.runpod.net/")],
        [InlineKeyboardButton("🧠 CivitAI", url=f"{base}-8082.proxy.runpod.net/")],
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
    track_message(uid, update.message.message_id)
    msg = await update.message.reply_text(f"🤖 **NeuroGraph v8.3**", reply_markup=get_main_kb(uid), parse_mode="Markdown")
    track_message(uid, msg.message_id)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    uid = update.effective_user.id
    track_message(uid, update.message.message_id)
    msg = await update.message.reply_text("📥 Сохраняю...", reply_markup=get_main_kb(uid)) # КРЕПИМ МЕНЮ
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

# --- WEBAPP (FLUX + MEMORY) ---
async def handle_webapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    uid = update.effective_user.id
    track_message(uid, update.message.message_id)
    try:
        data = json.loads(update.effective_message.web_app_data.data)
        d = get_user_data(uid)
        d['flux_store'] = data
        save_user_data()
        
        m_upd = await update.message.reply_text("💾 Настройки обновлены! Кнопка 'Пульт' обновлена.", reply_markup=get_main_kb(uid))
        track_message(uid, m_upd.message_id)

        # Preview Refs
        active_refs = [r for r in data['refs'] if r['active']]
        if active_refs:
            for r in active_refs:
                try:
                    img_data = get_view(r['image'], "", "input")
                    m = await context.bot.send_photo(uid, img_data, caption=f"Ref {r['idx']}")
                    track_message(uid, m.message_id)
                except: pass

        # Run
        batch = d['batch']
        msg = await update.message.reply_text(f"🎬 Flux Pro: {batch}x {data['res']}", reply_markup=stop_kb())
        track_message(uid, msg.message_id)
        asyncio.create_task(run_flux_batch(context, uid, data, batch, msg))
        
    except Exception as e:
        m = await update.message.reply_text(f"WebApp Error: {e}", reply_markup=get_main_kb(uid))
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
            save_user_data()
            m = await update.message.reply_text(f"🔢 Batch: {d['batch']}", reply_markup=get_main_kb(uid))
        else: m = await update.message.reply_text("Введите число", reply_markup=get_main_kb(uid))
        track_message(uid, m.message_id)
        return

    # 🧱 BUILD: ожидание имени пресета
    bs = d.get('build_state')
    if bs and bs.get('step') == 'name':
        preset_name = text.strip()
        if not preset_name or len(preset_name) > 30:
            m = await update.message.reply_text("❌ Имя от 1 до 30 символов", reply_markup=get_main_kb(uid))
            track_message(uid, m.message_id)
            return
        key = fd_build_preset(preset_name, bs['model'], bs['vae'], bs['encoder'])
        d['build_state'] = None
        save_user_data()
        if key:
            m = await update.message.reply_text(
                f"✅ Пресет <b>{preset_name}</b> собран!\n🔑 <code>{key}</code>\n\nСкачать: /dl → Custom",
                parse_mode="HTML", reply_markup=get_main_kb(uid)
            )
        else:
            m = await update.message.reply_text("❌ Ошибка сборки", reply_markup=get_main_kb(uid))
        track_message(uid, m.message_id)
        return
    
    if d.get('awaiting_dataset_name'):
        d['dataset_name'] = text
        d['awaiting_dataset_name'] = False
        save_user_data()
        m = await update.message.reply_text(f"🏷 Set: {text}", reply_markup=get_main_kb(uid))
        track_message(uid, m.message_id)
        return

    if d['awaiting_lora']:
        try:
            val = float(text.replace(",", "."))
            d['loras'][d['awaiting_lora']] = val
            d['awaiting_lora'] = None
            save_user_data()
            m = await update.message.reply_text("🎛 Mixer:", reply_markup=get_lora_kb(uid))
        except: m = await update.message.reply_text("Число!", reply_markup=get_lora_kb(uid))
        track_message(uid, m.message_id)
        return

    # COMMANDS
    if text == "🗑 ОЧИСТИТЬ":
        # 🧼 БУЛЬДОЗЕР: Чистим все подряд, игнорируем ошибки
        for mid in reversed(d['msg_ids']):
            try: 
                await context.bot.delete_message(uid, mid)
            except: 
                pass # Просто идем дальше
        d['msg_ids'] = []
        m = await context.bot.send_message(uid, "🧹 Чат очищен", reply_markup=get_main_kb(uid))
        track_message(uid, m.message_id)

    elif text == "🚀 ГЕНЕРАЦИЯ":
        if d['wf'] == 'flux':
            if d['flux_store']:
                data = d['flux_store']
                batch = d['batch']
                m = await update.message.reply_text(f"🚀 Flux {batch}x ({data['res']})...", reply_markup=stop_kb())
                track_message(uid, m.message_id)
                asyncio.create_task(run_flux_batch(context, uid, data, batch, m))
            else:
                m = await update.message.reply_text("⚠️ Сначала настрой через Пульт!", reply_markup=get_main_kb(uid))
                track_message(uid, m.message_id)
        else:
            d['_legacy_prompt'] = None
            cfg = WORKFLOWS[d['wf']]
            if cfg['need_photo'] and not d['image']:
                m = await update.message.reply_text("⚠️ Нужно фото!", reply_markup=get_main_kb(uid))
                track_message(uid, m.message_id)
            else:
                asyncio.create_task(run_legacy_batch(context, uid, update))

    elif text == "🎛 LORA MIXER":
        m = await update.message.reply_text("🎛 Выбери Лору:", reply_markup=get_lora_kb(uid))
        track_message(uid, m.message_id)

    elif text == "🌐 Ссылки":
        m = await update.message.reply_text("Links:", reply_markup=get_links_kb())
        track_message(uid, m.message_id)

    elif text == "📥 Загрузчик":
        await cmd_dl(update, context)

    elif text == "📁 История":
        hist = d.get('history', [])
        if not hist:
            m = await update.message.reply_text("💭 Нет истории", reply_markup=get_main_kb(uid))
            track_message(uid, m.message_id)
        else:
            items = hist[-10:]
            media = []
            for h in items:
                try:
                    idata = get_view(h['filename'], h['subfolder'], h['type'])
                    media.append(InputMediaPhoto(idata))
                except: pass
            if media:
                msgs = await context.bot.send_media_group(uid, media)
                for mm in msgs: track_message(uid, mm.message_id)
            else:
                m = await update.message.reply_text("⚠️ Файлы недоступны", reply_markup=get_main_kb(uid))
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
        save_user_data()
        m = await update.message.reply_text(f"🔄 Режим: **{WORKFLOWS[d['wf']]['name']}**", reply_markup=get_main_kb(uid), parse_mode="Markdown")
        track_message(uid, m.message_id)

    elif "Режим:" in text:
        d['mode'] = 'nsfw' if d['mode'] == 'normal' else 'normal'
        save_user_data()
        m = await update.message.reply_text(f"Режим: {d['mode'].upper()}", reply_markup=get_main_kb(uid))
        track_message(uid, m.message_id)

    else:
        if d['wf'] != 'flux':
            d['_legacy_prompt'] = text
            cfg = WORKFLOWS[d['wf']]
            if cfg['need_photo'] and not d['image']:
                m = await update.message.reply_text("⚠️ Нужно фото!", reply_markup=get_main_kb(uid))
                track_message(uid, m.message_id)
            else:
                asyncio.create_task(run_legacy_batch(context, uid, update))

# --- EXECUTION ---
async def run_workflow(context, uid, wf, batch_idx, user_prompt=None, status_msg=None, batch_label=""):
    start_time = time.time()
    res = queue_prompt(wf)
    if 'error' in res:
        return False, f"❌ {res['error']}", None

    pid = res['prompt_id']
    ws_url = f"ws://{COMFY_SERVER}/ws?clientId={CLIENT_ID}"

    # --- Вспомогательная: получение и обработка результата ---
    async def _process_result(history_data):
        try:
            out = history_data.get('outputs', {})
            if not out:
                return False, "❌ Нет outputs в результате", None

            found = False
            duration = time.time() - start_time
            
            used_seed = None
            for nid_check in ["117", "122"]:
                if nid_check in wf and "seed" in wf[nid_check].get("inputs", {}):
                    used_seed = wf[nid_check]["inputs"]["seed"]
                    break

            caption = f"✅ {batch_idx} | ⏱ {duration:.1f}s"
            if used_seed is not None:
                caption += f" | 🎲 {used_seed}"
            if user_prompt:
                caption += f"\n\n📝 {html.escape(user_prompt[:800])}"
            else:
                for nid, dat in out.items():
                    if 'text' in dat:
                        val = dat['text']
                        txt = str(val[0] if isinstance(val, list) else val)[:800]
                        caption += f"\n\n📝 {html.escape(txt)}"
                        break

            for nid in out:
                if 'images' in out[nid]:
                    for img in out[nid]['images']:
                        try:
                            idata = get_view(img['filename'], img['subfolder'], img['type'])
                            m = await context.bot.send_photo(uid, idata, caption=caption, parse_mode="HTML", reply_markup=get_main_kb(uid))
                            track_message(uid, m.message_id)
                            found = True
                            d = get_user_data(uid)
                            d.setdefault('history', []).append({"filename": img['filename'], "subfolder": img['subfolder'], "type": img['type']})
                            if len(d['history']) > 20: d['history'] = d['history'][-20:]
                            save_user_data()
                        except Exception as img_err:
                            print(f"⚠️ Failed to send image: {img_err}")
            
            return found, None, used_seed
        except Exception as e:
            print(f"❌ Error processing results: {e}")
            traceback.print_exc()
            return False, f"❌ Ошибка обработки: {e}", None

    # --- Вспомогательная: проверка history и возврат результата ---
    def _check_history():
        h = get_history(pid)
        if pid in h:
            return h[pid]
        return None

    # --- Основной цикл: WebSocket с fallback на polling ---
    try:
        async with websockets.connect(ws_url, close_timeout=2) as ws:
            last_update = 0
            while True:
                if time.time() - start_time > GEN_TIMEOUT:
                    try: urllib.request.urlopen(urllib.request.Request(f"http://{COMFY_SERVER}/interrupt", method='POST'))
                    except: pass
                    return False, f"⏰ Таймаут ({GEN_TIMEOUT}s)", None

                try:
                    # Увеличим timeout, чтобы дожидаться долгих шагов генерации
                    raw = await asyncio.wait_for(ws.recv(), timeout=20)
                except asyncio.TimeoutError:
                    # Каждые 20 сек проверяем history напрямую (fallback)
                    result_data = _check_history()
                    if result_data:
                        return await _process_result(result_data)
                    continue

                if isinstance(raw, bytes):
                    continue

                try:
                    msg = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    continue

                msg_type = msg.get("type", "")
                logging.error(f"WS RAW TYPE: {msg_type} | PID: {pid} | Data: {msg.get('data')}")

                if msg_type == "progress":
                    pd = msg.get("data", {})
                    if pd.get("prompt_id", pid) == pid:
                        step = pd.get("value", 0)
                        max_steps = pd.get("max", 1)
                        pct = int(step / max_steps * 100) if max_steps > 0 else 0
                        now = time.time()
                        if status_msg and (now - last_update >= 2 or step == max_steps):
                            try:
                                progress_text = f"🎬 {batch_label} | {step}/{max_steps} ({pct}%)" if batch_label else f"⏳ {step}/{max_steps} ({pct}%)"
                                await status_msg.edit_text(progress_text, reply_markup=stop_kb())
                                last_update = now
                            except Exception as uerr:
                                logging.error(f"UPDATE PROGRESS ERROR: {uerr}")

                elif msg_type == "executed" and msg.get("data", {}).get("prompt_id") == pid:
                    # Генерация завершена — ждём history с увеличенным таймаутом (до 60 секунд)
                    for _ in range(30):
                        result_data = _check_history()
                        if result_data:
                            return await _process_result(result_data)
                        await asyncio.sleep(2)
                    return False, "❌ History не появился после executed (таймаут 60с)", None

                elif msg_type == "execution_error" and msg.get("data", {}).get("prompt_id") == pid:
                    err_msg = msg.get("data", {}).get("exception_message", "Execution error")
                    return False, f"❌ {err_msg}", None

    except Exception as ws_err:
        print(f"⚠️ WebSocket failed: {ws_err}, using polling fallback")

    # --- Fallback: polling без WebSocket ---
    while True:
        if time.time() - start_time > GEN_TIMEOUT:
            try: urllib.request.urlopen(urllib.request.Request(f"http://{COMFY_SERVER}/interrupt", method='POST'))
            except: pass
            return False, f"⏰ Таймаут ({GEN_TIMEOUT}s)", None
        result_data = _check_history()
        if result_data:
            return await _process_result(result_data)
        await asyncio.sleep(2)

def stop_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⛔ СТОП", callback_data="stop_gen")]])

async def run_flux_batch(context, uid, data, batch, status_msg):
    cancel_flags[uid] = False
    healthy, health_err = check_comfy_health()
    if not healthy:
        try: await status_msg.edit_text(health_err)
        except: pass
        return
    user_prompt = data.get("pos")
    for i in range(batch):
        if cancel_flags.get(uid):
            m = await context.bot.send_message(uid, "⛔ Остановлено", reply_markup=get_main_kb(uid))
            track_message(uid, m.message_id)
            break
        try: await status_msg.edit_text(f"🎬 Flux {i+1}/{batch}...", reply_markup=stop_kb())
        except: pass
        d = get_user_data(uid)
        with open(WORKFLOWS["flux"]["file"], "r", encoding="utf-8") as f:
            wf = json.load(f)
        wf = apply_flux_settings(wf, data, dataset_name=d['dataset_name'], batch_idx=i+1)
        try:
            found, err, seed = await run_workflow(context, uid, wf, f"{i+1}/{batch}", user_prompt=user_prompt, status_msg=status_msg, batch_label=f"Flux {i+1}/{batch}")
            if err:
                m = await context.bot.send_message(uid, err, reply_markup=get_main_kb(uid))
                track_message(uid, m.message_id)
                break
        except Exception as e:
            m = await context.bot.send_message(uid, f"Runtime: {e}", reply_markup=get_main_kb(uid))
            track_message(uid, m.message_id)
            break
    try: await status_msg.delete()
    except: pass

async def run_legacy_batch(context, uid, update):
    cancel_flags[uid] = False
    d = get_user_data(uid)
    cfg = WORKFLOWS[d['wf']]
    prompt_txt = d.get('_legacy_prompt') or (PROMPT_NORMAL if d['mode'] == 'normal' else PROMPT_NSFW)
    batch = d['batch']

    status = await update.message.reply_text(f"🚀 {batch}x {cfg['name']}...", reply_markup=stop_kb())
    track_message(uid, status.message_id)

    healthy, health_err = check_comfy_health()
    if not healthy:
        try: await status.edit_text(health_err)
        except: pass
        return

    files = get_available_loras()
    for i in range(batch):
        if cancel_flags.get(uid):
            m = await context.bot.send_message(uid, "⛔ Остановлено", reply_markup=get_main_kb(uid))
            track_message(uid, m.message_id)
            break
        try: await status.edit_text(f"🚀 {i+1}/{batch} {cfg['name']}...", reply_markup=stop_kb())
        except: pass

        with open(cfg['file'], "r") as f: wf = json.load(f)
        
        nid = find_node_id(wf, ["Power Lora Loader (rgthree)"])
        if nid:
            for slot in range(1, 5):
                idx = slot - 1
                if idx < len(files):
                    if d['loras'].get(slot, 0.0) > 0:
                        wf[nid]["inputs"][f"lora_{slot}"] = {"on": True, "lora": files[idx], "strength": d['loras'][slot]}
                    else: wf[nid]["inputs"][f"lora_{slot}"] = {"on": False}

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
            wf["211"]["inputs"]["value"] = f"{d['dataset_name']}_{i+1:03d}"

        try:
            found, err, seed = await run_workflow(context, uid, wf, f"{i+1}/{batch}", status_msg=status, batch_label=f"{cfg['name']} {i+1}/{batch}")
            if err:
                m = await context.bot.send_message(uid, err, reply_markup=get_main_kb(uid))
                track_message(uid, m.message_id)
                break
        except Exception as e:
            m = await context.bot.send_message(uid, f"Runtime: {e}", reply_markup=get_main_kb(uid))
            track_message(uid, m.message_id)
            break

    try: await status.delete()
    except: pass

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
            save_user_data()
            await q.message.delete()
            m = await context.bot.send_message(uid, f"🔢 Batch: **{d['batch']}**", reply_markup=get_main_kb(uid), parse_mode="Markdown")
            track_message(uid, m.message_id)
    
    elif q.data.startswith("edit_lora_"):
        slot = int(q.data.split("_")[2])
        d['awaiting_lora'] = slot
        files = get_available_loras()
        idx = slot - 1
        lname = files[idx] if idx < len(files) else f"Slot {slot}"
        await q.message.edit_text(f"✍️ **{lname}**\nВведите вес (0.1 - 1.0):", parse_mode="Markdown")

    elif q.data == "stop_gen":
        cancel_flags[uid] = True
        try: urllib.request.urlopen(urllib.request.Request(f"http://{COMFY_SERVER}/interrupt", method='POST'))
        except: pass
        try: await q.message.edit_text("⛔ Останавливаю...")
        except: pass

    elif q.data in ["close_links", "close_lora"]: 
        await q.message.delete()
        m = await context.bot.send_message(uid, "✅ Меню активно", reply_markup=get_main_kb(uid))
        track_message(uid, m.message_id)

    # --- DOWNLOADER CALLBACKS ---
    elif q.data.startswith("dlcat_"):
        cat = q.data[6:]
        presets_list = get_presets_by_category(cat)
        if not presets_list:
            await q.message.edit_text("📭 Нет пресетов в этой категории")
            return
        kb = []
        for i in range(0, len(presets_list), 2):
            row = []
            for key, info in presets_list[i:i+2]:
                row.append(InlineKeyboardButton(
                    f"{info['name']} {info.get('size','')}",
                    callback_data=f"dlpreset_{key}"
                ))
            kb.append(row)
        kb.append([InlineKeyboardButton("🔙 Назад", callback_data="dlback")])
        cats_data = load_presets().get("categories", {})
        icon = cats_data.get(cat, {}).get("icon", "📦")
        await q.message.edit_text(
            f"{icon} **{cat}** — выбери пресет:",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )

    elif q.data.startswith("dlpreset_"):
        key = q.data[9:]
        info = get_preset_info(key)
        if not info:
            await q.message.edit_text("❌ Пресет не найден")
            return
        n_files = len(info.get('files', []))
        text_msg = (
            f"📦 <b>{info['name']}</b>\n"
            f"📂 {n_files} файлов, {info.get('size', '?')}\n"
            f"🏷 {info.get('category', 'Custom')}"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬇️ Скачать", callback_data=f"dlconfirm_{key}")],
            [InlineKeyboardButton("🔙 Назад", callback_data=f"dlcat_{info.get('category','Custom')}")]
        ])
        await q.message.edit_text(text_msg, reply_markup=kb, parse_mode="HTML")

    elif q.data.startswith("dlconfirm_"):
        key = q.data[10:]
        info = get_preset_info(key)
        if not info:
            await q.message.edit_text("❌ Пресет не найден")
            return
        await q.message.edit_text(
            f"🚀 Скачиваю: <b>{info['name']}</b>\n📦 Подготовка...",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="dlcancel")]]),
            parse_mode="HTML"
        )
        asyncio.create_task(_run_preset_download(context, uid, key, q.message))

    elif q.data == "dlcancel":
        download_cancel_flags[uid] = True
        try:
            await q.message.edit_text("⛔ Отменяю загрузку...")
        except: pass

    elif q.data == "dlback":
        await _show_dl_menu(q.message, edit=True)

    # --- BUILD (CONSTRUCTOR) CALLBACKS ---
    elif q.data.startswith("bm_"):
        # Выбрана модель → показать VAE
        model_key = q.data[3:]
        d.setdefault('build_state', {})['model'] = model_key
        d['build_state']['step'] = 'vae'
        comp = get_component('models', model_key)
        model_name = comp['name'] if comp else model_key
        
        vae_list = get_components('vae')
        kb = []
        for i in range(0, len(vae_list), 2):
            row = []
            for vk, vi in vae_list[i:i+2]:
                label = vi['name'][:25]
                row.append(InlineKeyboardButton(label, callback_data=f"bv_{vk}"))
            kb.append(row)
        kb.append([InlineKeyboardButton("❌ Отмена", callback_data="bcancel")])
        await q.message.edit_text(
            f"🧱 **Конструктор**\n✅ Модель: {model_name}\n\nШаг 2/4: Выбери **VAE**:",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
        )

    elif q.data.startswith("bv_"):
        # Выбран VAE → показать энкодеры
        vae_key = q.data[3:]
        d.setdefault('build_state', {})['vae'] = vae_key
        d['build_state']['step'] = 'encoder'
        comp = get_component('vae', vae_key)
        vae_name = comp['name'] if comp else vae_key
        model_comp = get_component('models', d['build_state'].get('model', ''))
        model_name = model_comp['name'] if model_comp else '?'
        
        enc_list = get_components('text_encoders')
        kb = []
        for i in range(0, len(enc_list), 2):
            row = []
            for ek, ei in enc_list[i:i+2]:
                label = ei['name'][:25]
                row.append(InlineKeyboardButton(label, callback_data=f"be_{ek}"))
            kb.append(row)
        kb.append([InlineKeyboardButton("❌ Отмена", callback_data="bcancel")])
        await q.message.edit_text(
            f"🧱 **Конструктор**\n✅ Модель: {model_name}\n✅ VAE: {vae_name}\n\nШаг 3/4: Выбери **энкодер**:",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
        )

    elif q.data.startswith("be_"):
        # Выбран энкодер → запросить имя
        enc_key = q.data[3:]
        d.setdefault('build_state', {})['encoder'] = enc_key
        d['build_state']['step'] = 'name'
        
        model_comp = get_component('models', d['build_state'].get('model', ''))
        vae_comp = get_component('vae', d['build_state'].get('vae', ''))
        enc_comp = get_component('text_encoders', enc_key)
        
        await q.message.edit_text(
            f"🧱 **Конструктор**\n"
            f"✅ Модель: {model_comp['name'] if model_comp else '?'}\n"
            f"✅ VAE: {vae_comp['name'] if vae_comp else '?'}\n"
            f"✅ Энкодер: {enc_comp['name'] if enc_comp else '?'}\n\n"
            f"Шаг 4/4: **Введи имя** пресета:",
            parse_mode="Markdown"
        )

    elif q.data == "bcancel":
        d['build_state'] = None
        try:
            await q.message.edit_text("❌ Конструктор отменён")
        except: pass

# ==========================================
# 📥 DOWNLOADER COMMANDS
# ==========================================

async def _show_dl_menu(message, edit=False):
    """Показывает главное меню загрузчика (категории)."""
    cats = get_categories_with_counts()
    if not cats:
        text = "📭 Пресеты не найдены. Проверь presets.json"
        if edit:
            await message.edit_text(text)
        else:
            await message.reply_text(text)
        return
    
    kb = []
    for i in range(0, len(cats), 3):
        row = []
        for cat, icon, count in cats[i:i+3]:
            row.append(InlineKeyboardButton(f"{icon} {cat} ({count})", callback_data=f"dlcat_{cat}"))
        kb.append(row)
    
    text = "📥 **Загрузчик моделей**\nВыбери категорию:"
    if edit:
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    else:
        return await message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


async def cmd_dl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /dl — открывает меню загрузчика."""
    if not await check_auth(update): return
    uid = update.effective_user.id
    track_message(uid, update.message.message_id)
    m = await _show_dl_menu(update.message)
    if m:
        track_message(uid, m.message_id)


async def cmd_add_preset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/add_preset <Имя> <URL> <folder> — добавляет кастомный пресет."""
    if not await check_auth(update): return
    uid = update.effective_user.id
    track_message(uid, update.message.message_id)
    
    args = context.args
    if not args or len(args) < 3:
        m = await update.message.reply_text(
            "📝 Формат:\n`/add_preset Имя URL папка`\n\n"
            "Папки: `diffusion_models`, `text_encoders`, `vae`, `loras`, `checkpoints`, `upscale_models`\n\n"
            "Пример:\n`/add_preset MyLora https://hf.co/.../lora.safetensors loras`",
            parse_mode="Markdown",
            reply_markup=get_main_kb(uid)
        )
        track_message(uid, m.message_id)
        return
    
    name = args[0]
    url = args[1]
    folder = args[2] if len(args) > 2 else "diffusion_models"
    
    valid_folders = ["diffusion_models", "text_encoders", "vae", "loras", 
                     "checkpoints", "upscale_models", "controlnet", "latent_upscale_models"]
    if folder not in valid_folders:
        m = await update.message.reply_text(
            f"❌ Неверная папка: `{folder}`\n\nДоступные: {', '.join(f'`{f}`' for f in valid_folders)}",
            parse_mode="Markdown", reply_markup=get_main_kb(uid)
        )
        track_message(uid, m.message_id)
        return
    
    if not url.startswith("http"):
        m = await update.message.reply_text("❌ URL должен начинаться с http", reply_markup=get_main_kb(uid))
        track_message(uid, m.message_id)
        return
    
    key = f"CUSTOM_{name.upper().replace(' ', '_')}"
    fd_add_preset(key, name, "Custom", [{"url": url, "folder": folder, "filename": None}])
    
    m = await update.message.reply_text(
        f"✅ Пресет добавлен!\n📦 {name}\n🔑 `{key}`\n📂 {folder}",
        parse_mode="Markdown", reply_markup=get_main_kb(uid)
    )
    track_message(uid, m.message_id)


async def cmd_dl_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/dl_url <URL> [folder] — скачивает по прямой ссылке."""
    if not await check_auth(update): return
    uid = update.effective_user.id
    track_message(uid, update.message.message_id)
    
    args = context.args
    if not args:
        m = await update.message.reply_text(
            "📝 Формат: `/dl_url URL [папка]`\nПо умолчанию: `diffusion_models`",
            parse_mode="Markdown", reply_markup=get_main_kb(uid)
        )
        track_message(uid, m.message_id)
        return
    
    url = args[0]
    folder = args[1] if len(args) > 1 else "diffusion_models"
    
    msg = await update.message.reply_text(
        f"📥 Скачиваю...\n🔗 `{url[:60]}...`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="dlcancel")]])
    )
    track_message(uid, msg.message_id)
    
    last_edit = [0.0]
    
    async def on_progress(dl_bytes, total_bytes, filename):
        now = time.time()
        if now - last_edit[0] < 3:
            return
        last_edit[0] = now
        if total_bytes > 0:
            pct = int(dl_bytes / total_bytes * 100)
            mb_dl = dl_bytes / (1024 * 1024)
            mb_total = total_bytes / (1024 * 1024)
            bar = _progress_bar(pct)
            text = f"📥 {filename}\n{bar} {pct}%\n💾 {mb_dl:.0f} / {mb_total:.0f} MB"
        else:
            mb_dl = dl_bytes / (1024 * 1024)
            text = f"📥 {filename}\n💾 {mb_dl:.0f} MB"
        try:
            await msg.edit_text(text, reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⛔ Отмена", callback_data="dlcancel")]]
            ))
        except: pass
    
    try:
        status, filename = await fd_download_url(url, folder, on_progress=on_progress, uid=uid)
        if status == "SKIP":
            await msg.edit_text(f"⏭️ Уже существует: `{filename}`", parse_mode="Markdown")
        else:
            await msg.edit_text(f"✅ Скачано: `{filename}`", parse_mode="Markdown")
    except RuntimeError as e:
        await msg.edit_text(f"❌ {e}")


async def _run_preset_download(context, uid, preset_key, status_msg):
    """Фоновая задача: скачивание пресета с обновлением прогресса."""
    info = get_preset_info(preset_key)
    if not info:
        try: await status_msg.edit_text("❌ Пресет не найден")
        except: pass
        return
    
    last_edit = [0.0]
    stop_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="dlcancel")]])
    
    async def on_progress(cur_file, total_files, dl_bytes, total_bytes, filename):
        now = time.time()
        if now - last_edit[0] < 3:
            return
        last_edit[0] = now
        
        if total_bytes > 0:
            pct = int(dl_bytes / total_bytes * 100)
            bar = _progress_bar(pct)
            text = (
                f"📥 <b>{info['name']}</b>\n"
                f"📦 {cur_file}/{total_files} | {filename}\n"
                f"{bar} {pct}%"
            )
        else:
            mb = dl_bytes / (1024 * 1024)
            text = (
                f"📥 <b>{info['name']}</b>\n"
                f"📦 {cur_file}/{total_files} | {filename}\n"
                f"💾 {mb:.0f} MB"
            )
        try:
            await status_msg.edit_text(text, reply_markup=stop_kb, parse_mode="HTML")
        except: pass
    
    try:
        result = await download_preset(preset_key, on_progress=on_progress, uid=uid)
        
        parts = [f"✅ <b>{info['name']}</b> — готово!\n"]
        if result["downloaded"]:
            parts.append(f"📥 Скачано: {len(result['downloaded'])}")
        if result["skipped"]:
            parts.append(f"⏭️ Пропущено: {len(result['skipped'])}")
        if result["failed"]:
            parts.append(f"❌ Ошибки: {len(result['failed'])}")
            for err in result["failed"][:5]:
                parts.append(f"   • {err[:80]}")
        
        await status_msg.edit_text("\n".join(parts), parse_mode="HTML")
    except Exception as e:
        try:
            await status_msg.edit_text(f"❌ Ошибка: {e}")
        except: pass
    
    m = await context.bot.send_message(uid, "✅ Меню активно", reply_markup=get_main_kb(uid))
    track_message(uid, m.message_id)


def _progress_bar(percent: int, length: int = 10) -> str:
    """Генерирует текстовый прогресс-бар: [█████░░░░░]"""
    filled = int(length * percent / 100)
    return "[" + "█" * filled + "░" * (length - filled) + "]"


async def cmd_build(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /build — конструктор пресетов из компонентов."""
    if not await check_auth(update): return
    uid = update.effective_user.id
    track_message(uid, update.message.message_id)
    d = get_user_data(uid)
    d['build_state'] = {'step': 'model'}
    
    models = get_components('models')
    if not models:
        m = await update.message.reply_text("📭 Каталог компонентов пуст", reply_markup=get_main_kb(uid))
        track_message(uid, m.message_id)
        d['build_state'] = None
        return
    
    kb = []
    for i in range(0, len(models), 2):
        row = []
        for mk, mi in models[i:i+2]:
            label = mi['name'][:25]
            row.append(InlineKeyboardButton(label, callback_data=f"bm_{mk}"))
        kb.append(row)
    kb.append([InlineKeyboardButton("❌ Отмена", callback_data="bcancel")])
    
    m = await update.message.reply_text(
        "🧱 **Конструктор пресетов**\n\nШаг 1/4: Выбери **модель**:",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
    )
    track_message(uid, m.message_id)


if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('dl', cmd_dl))
    app.add_handler(CommandHandler('build', cmd_build))
    app.add_handler(CommandHandler('add_preset', cmd_add_preset))
    app.add_handler(CommandHandler('dl_url', cmd_dl_url))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_msg))
    print(f"✅ Bot v8.4 Started on {RUNPOD_ID}")
    app.run_polling()
