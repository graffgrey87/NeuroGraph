import websocket, uuid, json, urllib.request, urllib.parse, requests, random, os, time, traceback, sys
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# === КОНФИГ ===
COMFY_PORT = "3000" 
COMFY_SERVER = f"127.0.0.1:{COMFY_PORT}"
BOT_TOKEN = os.getenv("TG_TOKEN")
RUNPOD_ID = os.environ.get("RUNPOD_POD_ID", "127.0.0.1")
# Админы из переменной среды
raw_ids = os.getenv("ADMIN_ID")
ALLOWED_USERS = [int(x) for x in raw_ids.split(",") if x.strip().isdigit()] if raw_ids else []

if not BOT_TOKEN:
    sys.exit("❌ TG_TOKEN не найден")

# === DATA ===
user_data = {}
WORKFLOWS = {
    "edit": {"file": "workflow_api.json", "name": "🎨 Редакт (Qwen)", "need_photo": True},
    "gen":  {"file": "workflow_gen.json",  "name": "✨ Генерация (Flux)", "need_photo": False}
}

def get_data(uid):
    if uid not in user_data:
        # msg_ids - храним последние 50 ID для удаления
        user_data[uid] = {'image': None, 'wf': 'edit', 'batch': 1, 'msg_ids': []}
    return user_data[uid]

def track_msg(uid, msg_id):
    d = get_data(uid)
    d['msg_ids'].append(msg_id)
    if len(d['msg_ids']) > 50: d['msg_ids'].pop(0)

# === SMART MODEL FIXER (То, что мы делали вручную) ===
def smart_fix_models(workflow):
    print("🔍 Smart Fixer: Проверка путей...")
    maps = {
        'VAELoader': ('vae', 'vae_name'),
        'CLIPLoader': ('clip', 'clip_name'),
        'DualCLIPLoader': ('clip', 'clip_name1'),
        'CheckpointLoaderSimple': ('checkpoints', 'ckpt_name'),
        'DiffusionModelLoaderKJ': ('diffusion_models', 'model_name'),
        'LoraLoaderModelOnly': ('loras', 'lora_name'),
        'LoraLoader': ('loras', 'lora_name')
    }
    base = '/workspace/ComfyUI/models'
    for nid, node in workflow.items():
        if node.get('class_type') in maps:
            sub, key = maps[node['class_type']]
            if key in node.get('inputs', {}):
                val = node['inputs'][key]
                path = os.path.join(base, sub)
                if os.path.exists(path):
                    # Ищем любой файл в папке, если точного совпадения нет
                    files = [f for f in os.listdir(path) if not f.startswith('.')]
                    if files and val not in files:
                        print(f"🔧 Fix: Меняю {val} -> {files[0]}")
                        node['inputs'][key] = files[0]
    return workflow

# === API ===
def upload_img(data, name):
    try:
        resp = requests.post(f"http://{COMFY_SERVER}/upload/image", 
                             files={'image': (name, data)}, 
                             data={'type': 'input', 'overwrite': 'true'})
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
        with urllib.request.urlopen(f"http://{COMFY_SERVER}/history/{pid}") as r:
            return json.loads(r.read())
    except: return {}

def get_view(fname, sub, type):
    q = urllib.parse.urlencode({"filename": fname, "subfolder": sub, "type": type})
    with urllib.request.urlopen(f"http://{COMFY_SERVER}/view?{q}") as r:
        return r.read()

# === BOT LOGIC ===
async def start(update, context):
    uid = update.effective_user.id
    if uid not in ALLOWED_USERS: return
    kb = [[KeyboardButton("🚀 ГЕНЕРАЦИЯ"), KeyboardButton("🗑 ОЧИСТИТЬ")],
          [KeyboardButton(f"🔄 WF"), KeyboardButton(f"🔢 Батч")]]
    m = await update.message.reply_text(f"✅ Бот активен (Port {COMFY_PORT})", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    track_msg(uid, update.message.message_id)
    track_msg(uid, m.message_id)

async def handle_photo(update, context):
    uid = update.effective_user.id
    if uid not in ALLOWED_USERS: return
    track_msg(uid, update.message.message_id)
    
    f = await update.message.photo[-1].get_file()
    fname = f"img_{uid}.jpg"
    b = await f.download_as_bytearray()
    
    if upload_img(b, fname):
        get_data(uid)['image'] = fname
        m = await update.message.reply_text("✅ Фото принято")
        track_msg(uid, m.message_id)
    else:
        m = await update.message.reply_text("❌ Ошибка загрузки в ComfyUI")
        track_msg(uid, m.message_id)

async def handle_msg(update, context):
    uid = update.effective_user.id
    if uid not in ALLOWED_USERS: return
    text = update.message.text
    d = get_data(uid)
    track_msg(uid, update.message.message_id)

    if text == "🚀 ГЕНЕРАЦИЯ":
        wf_conf = WORKFLOWS[d['wf']]
        if wf_conf['need_photo'] and not d['image']:
            m = await update.message.reply_text("⚠️ Нужно фото!")
            track_msg(uid, m.message_id)
            return

        m = await update.message.reply_text(f"🚀 Запуск {d['batch']} шт...")
        track_msg(uid, m.message_id)

        for _ in range(d['batch']):
            try:
                # Читаем файл
                if not os.path.exists(wf_conf['file']):
                    await update.message.reply_text(f"❌ Нет файла {wf_conf['file']}")
                    break

                with open(wf_conf['file'], 'r') as f: wf = json.load(f)
                
                # 1. ЧИНИМ ПУТИ (Smart Fixer)
                wf = smart_fix_models(wf)
                
                # 2. ПОДСТАВЛЯЕМ ФОТО
                for n in wf.values():
                    if n.get('class_type') == 'LoadImage':
                        n['inputs']['image'] = d['image']

                # 3. ЗАПУСК
                res = queue_prompt(wf)
                if 'error' in res:
                    await update.message.reply_text(f"Comfy Error: {res['error']}")
                    break
                
                pid = res['prompt_id']
                while True:
                    hist = get_history(pid)
                    if pid in hist: break
                    time.sleep(1)
                
                out = hist[pid]['outputs']
                found = False
                for nid in out:
                    if 'images' in out[nid]:
                        for img in out[nid]['images']:
                            img_data = get_view(img['filename'], img['subfolder'], img['type'])
                            s = await context.bot.send_photo(uid, img_data)
                            track_msg(uid, s.message_id)
                            found = True
                if not found:
                    await update.message.reply_text("⚠️ Генерация завершена, но фото нет.")

            except Exception as e:
                await update.message.reply_text(f"Crash: {e}")
                traceback.print_exc()

    elif text == "🗑 ОЧИСТИТЬ":
        # Чистим чат
        for mid in reversed(d['msg_ids']):
            try: await context.bot.delete_message(uid, mid)
            except: pass
        d['msg_ids'] = []
        m = await update.message.reply_text("🧹 Чисто")
        track_msg(uid, m.message_id)

    elif text == "🔄 WF":
        d['wf'] = 'gen' if d['wf'] == 'edit' else 'edit'
        m = await update.message.reply_text(f"Режим: {WORKFLOWS[d['wf']]['name']}")
        track_msg(uid, m.message_id)

    # ВВОД ЧИСЛА РУКАМИ
    elif text.isdigit():
        d['batch'] = int(text)
        m = await update.message.reply_text(f"🔢 Батч установлен: {text}")
        track_msg(uid, m.message_id)
    
    elif text == "🔢 Батч":
         m = await update.message.reply_text(f"Сейчас батч: {d['batch']}. Напиши число.")
         track_msg(uid, m.message_id)

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT, handle_msg))
    print(f"Bot active on {RUNPOD_ID}")
    app.run_polling()
