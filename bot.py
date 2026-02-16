import websocket, uuid, json, urllib.request, urllib.parse, requests, random, os, time, traceback, re, sys, html, asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# --- CONFIG ---
BOT_TOKEN = os.getenv("TG_TOKEN")
raw_ids = os.getenv("ADMIN_ID", "")
ALLOWED_USERS = [int(x) for x in raw_ids.split(",") if x.strip().isdigit()] if raw_ids else []

COMFY_PORT = "3000"
RUNPOD_ID = os.environ.get("RUNPOD_POD_ID", "127.0.0.1")
COMFY_SERVER = f"127.0.0.1:{COMFY_PORT}"
BASE_DIR = "/workspace"
CLIENT_ID = str(uuid.uuid4())
WEBAPP_URL = f"https://{RUNPOD_ID}-8099.proxy.runpod.net"

WORKFLOWS = {
    "edit": { "file": os.path.join(BASE_DIR, "workflow_api.json"), "name": "🎨 Редакт (Qwen)", "need_photo": True },
    "gen":  { "file": os.path.join(BASE_DIR, "workflow_gen.json"), "name": "✨ Генерация (Legacy)", "need_photo": False },
    "flux": { "file": os.path.join(BASE_DIR, "TI2I_Flux2_Klein.json"), "name": "🚀 Flux Pro", "need_photo": False }
}

PROMPT_NORMAL = "На фото крупным планом показана высокая девушка с изображения 1 которая __действие__ __место__. На ней __наряд__. Её наряд выполнен в __цвет__. Из украшений на ней __украшения__. Ракурс __ракурс__, __угол__, __крупность__ __выражения__. Фото в стиле __стиль__, реалистичное освещение."
PROMPT_NSFW = "На фото крупным планом показана высокая девушка с изображения 1, которая __действие_nsfw__ __место__. На ней __наряд_nsfw__. Она __доп_действие_nsfw__. Её наряд выполнен в __цвет__. Из украшений на ней __украшения__. Ракурс __ракурс__, __угол__, __крупность__ __выражения__. Фото в стиле __стиль__, реалистичное освещение."

user_data = {}

if not BOT_TOKEN: sys.exit("❌ TOKEN MISSING")

# --- UTILS ---
def get_user_data(uid):
    if uid not in user_data:
        user_data[uid] = {
            'image': None, 'mode': 'normal', 'wf': 'flux', 'batch': 1, 
            'dataset_name': 'Batch', 'msg_ids': [], 'loras': {1:0.0, 2:0.0, 3:0.0, 4:0.0},
            'awaiting_lora': None, 'awaiting_custom_batch': False, 'awaiting_dataset_name': False
        }
    return user_data[uid]

def track_message(uid, mid):
    d = get_user_data(uid)
    if mid not in d['msg_ids']: d['msg_ids'].append(mid)
    if len(d['msg_ids']) > 100: d['msg_ids'].pop(0)

async def check_auth(update):
    if ALLOWED_USERS and update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ Private Bot")
        return False
    return True

def upload_image(file_bytes, file_name):
    try:
        files = {'image': (file_name, file_bytes)}
        data = {'type': 'input', 'overwrite': 'true'}
        return requests.post(f"http://{COMFY_SERVER}/upload/image", files=files, data=data).json()
    except: return None

def queue_prompt(wf):
    try:
        data = json.dumps({"prompt": wf, "client_id": CLIENT_ID}).encode('utf-8')
        req = urllib.request.Request(f"http://{COMFY_SERVER}/prompt", data=data)
        return json.loads(urllib.request.urlopen(req).read())
    except Exception as e: return {'error': str(e)}

def get_history(pid):
    try:
        with urllib.request.urlopen(f"http://{COMFY_SERVER}/history/{pid}") as r: return json.loads(r.read())
    except: return {}

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

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    uid = update.effective_user.id
    msg = await update.message.reply_text(f"🤖 **NeuroGraph v6.1**\nPod: `{RUNPOD_ID}`", reply_markup=get_main_kb(uid), parse_mode="Markdown")
    track_message(uid, msg.message_id)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    uid = update.effective_user.id
    msg = await update.message.reply_text("📥 Сохраняю...")
    track_message(uid, msg.message_id)
    try:
        f = await update.message.photo[-1].get_file()
        fname = f"user_{uid}_{int(time.time())}.jpg"
        resp = upload_image(await f.download_as_bytearray(), fname)
        if resp:
            real = resp.get("name", fname)
            get_user_data(uid)['image'] = real
            await msg.edit_text(f"✅ Фото: `{real}`\nДоступно во всех режимах!", parse_mode="Markdown")
        else: await msg.edit_text("❌ Ошибка")
    except Exception as e: await msg.edit_text(f"Error: {e}")

# --- WEBAPP (FLUX PRO) ---
async def handle_webapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    uid = update.effective_user.id
    try:
        data = json.loads(update.effective_message.web_app_data.data)
        with open(WORKFLOWS["flux"]["file"], "r", encoding="utf-8") as f: wf = json.load(f)

        # 1. MODEL & SETTINGS
        # Diffusion (116:129)
        if "116:129" in wf:
            wf["116:129"]["inputs"]["model_name"] = data["ckpt"]
            wf["116:129"]["inputs"]["weight_dtype"] = data["dtype"]
            if "sage_attention" in wf["116:129"]["inputs"]:
                wf["116:129"]["inputs"]["sage_attention"] = data["sage"]
        
        # CLIP (116:120)
        if "116:120" in wf: wf["116:120"]["inputs"]["clip_name"] = data["clip"]
        
        # VAE (116:115)
        if "116:115" in wf: wf["116:115"]["inputs"]["vae_name"] = data["vae"]

        # 2. GENERAL
        wf["101"]["inputs"]["aspect_ratio"] = data["res"]
        wf["117"]["inputs"]["seed"] = int(data["seed"]) if int(data["seed"]) != -1 else random.randint(1, 10**15)
        wf["119"]["inputs"]["Xi"] = int(data["steps"]); wf["119"]["inputs"]["Xf"] = int(data["steps"])
        wf["118"]["inputs"]["Xi"] = float(data["cfg"]); wf["118"]["inputs"]["Xf"] = float(data["cfg"])
        wf["161"]["inputs"]["value"] = data["pos"]
        wf["162"]["inputs"]["value"] = data["neg"]
        
        # 3. CAMERA
        wf["146"]["inputs"]["value"] = int(data["rot"])
        wf["144"]["inputs"]["value"] = int(data["ang"])
        wf["151"]["inputs"]["value"] = int(data["dist"])

        # 4. INPAINT & REFS SCALE
        wf["228"]["inputs"]["Xi"] = float(data["ctx"]); wf["228"]["inputs"]["Xf"] = float(data["ctx"])
        wf["229"]["inputs"]["Xi"] = float(data["resc"]); wf["229"]["inputs"]["Xf"] = float(data["resc"])
        wf["139"]["inputs"]["Xi"] = float(data["rscale"]); wf["139"]["inputs"]["Xf"] = float(data["rscale"])

        # 5. LORAS
        if "153" in wf:
            for i in range(1,14): 
                if f"lora_{i}" in wf["153"]["inputs"]: wf["153"]["inputs"][f"lora_{i}"] = {"on": False}
            for i, l in enumerate(data["loras"]):
                wf["153"]["inputs"][f"lora_{i+1}"] = {"on": True, "lora": l["name"], "strength": l["weight"]}

        # 6. REFS (1-6)
        loaders = {1:"76", 2:"104", 3:"105", 4:"182", 5:"183", 6:"184"}
        for i in range(1,7):
            gid = 211+i
            if f"{gid}:214" in wf: wf[f"{gid}:214"]["inputs"]["value"] = False # Reset
        
        for r in data["refs"]:
            idx = r["idx"]
            gid = 211+idx
            if loaders[idx] in wf: wf[loaders[idx]]["inputs"]["image"] = r["image"]
            if f"{gid}:214" in wf: wf[f"{gid}:214"]["inputs"]["value"] = r["active"]
            if f"{gid}:213" in wf: wf[f"{gid}:213"]["inputs"]["switch"] = r["flip"]
            if f"{gid}:209" in wf: wf[f"{gid}:209"]["inputs"]["rotation"] = r["rot"]

        # RUN
        msg = await update.message.reply_text(f"🎬 Flux Pro: {data['res']}")
        asyncio.create_task(run_workflow(context, uid, wf, msg, 1))

    except Exception as e:
        await update.message.reply_text(f"WebApp Error: {e}")
        traceback.print_exc()

# --- TEXT & LEGACY ---
async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    uid = update.effective_user.id
    text = update.message.text
    d = get_user_data(uid)
    track_message(uid, update.message.message_id)

    # ... СЮДА ВСТАВИТЬ ЛОГИКУ BATCH/DATASET ИЗ 5.3 (Она в полном файле выше) ...
    # (Я сократил этот блок для читаемости, но в полной версии он есть)
    
    if text == "🚀 ГЕНЕРАЦИЯ":
        if d['wf'] == 'flux':
            m = await update.message.reply_text("⚠️ Flux используй через ПУЛЬТ!")
            track_message(uid, m.message_id)
        else:
            await run_legacy_gen(update, context, uid)

    elif "Режим:" in text:
        # Переключение
        keys = list(WORKFLOWS.keys())
        # ... Логика переключения ...
        await start(update, context)

    # Очистка, Ссылки и т.д.
    elif text == "🗑 ОЧИСТИТЬ":
        for mid in reversed(d['msg_ids']):
            try: await context.bot.delete_message(uid, mid)
            except: pass
        d['msg_ids'] = []
        await update.message.reply_text("🧹", reply_markup=get_main_kb(uid))

# --- EXECUTION ---
async def run_workflow(context, uid, wf, status_msg, batch_idx):
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
        for nid in out:
            if 'images' in out[nid]:
                for img in out[nid]['images']:
                    url = f"http://{COMFY_SERVER}/view?filename={img['filename']}&subfolder={img['subfolder']}&type={img['type']}"
                    dat = urllib.request.urlopen(url).read()
                    await context.bot.send_photo(uid, dat, caption=f"✅ Result {batch_idx}")
                    found = True
        
        if found: await status_msg.delete()
        else: await status_msg.edit_text("⚠️ No output")

    except Exception as e:
        await context.bot.send_message(uid, f"Runtime Error: {e}")

async def run_legacy_gen(update, context, uid):
    d = get_user_data(uid)
    cfg = WORKFLOWS[d['wf']]
    
    if cfg['need_photo'] and not d['image']:
        await update.message.reply_text("⚠️ Photo required!")
        return
        
    status = await update.message.reply_text(f"🚀 Running {d['batch']}x {cfg['name']}...")
    track_message(uid, status.message_id)

    # ГЕНЕРАЦИЯ БАТЧЕЙ (КАК В 5.3)
    for i in range(d['batch']):
        with open(cfg['file'], "r") as f: wf = json.load(f)
        
        if cfg['need_photo']:
            # Простой поиск нод LoadImage
            for nid, n in wf.items():
                if n.get("class_type") in ["LoadImage", "LoadImageMask"]: n["inputs"]["image"] = d['image']
        
        # Seed randomize
        for nid, n in wf.items():
            if n.get("class_type") in ["EasySeed", "Seed", "KSampler"]: 
                if "seed" in n["inputs"]: n["inputs"]["seed"] = random.randint(1, 10**15)

        asyncio.create_task(run_workflow(context, uid, wf, status, i+1))

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_msg))
    print(f"✅ Bot v6.1 Started on {RUNPOD_ID}")
    app.run_polling()