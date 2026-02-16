import websocket, uuid, json, urllib.request, urllib.parse, requests, random, os, time, traceback, re, sys, html, asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# ==========================================
# ⚙️ КОНФИГУРАЦИЯ
# ==========================================
BOT_TOKEN = os.getenv("TG_TOKEN")
# Список админов (из переменной окружения)
raw_ids = os.getenv("ADMIN_ID", "")
ALLOWED_USERS = [int(x) for x in raw_ids.split(",") if x.strip().isdigit()]

# ComfyUI
COMFY_PORT = "3000"
RUNPOD_ID = os.environ.get("RUNPOD_POD_ID", "127.0.0.1")
COMFY_SERVER = f"127.0.0.1:{COMFY_PORT}"
BASE_DIR = "/workspace"
CLIENT_ID = str(uuid.uuid4())

# WebApp
WEBAPP_PORT = "8099"
WEBAPP_URL = f"https://{RUNPOD_ID}-{WEBAPP_PORT}.proxy.runpod.net"

# Режимы работы
WORKFLOWS = {
    "edit": {
        "file": os.path.join(BASE_DIR, "workflow_api.json"), 
        "name": "🎨 Редакт (Qwen/Edit)", 
        "need_photo": True
    },
    "gen": {
        "file": os.path.join(BASE_DIR, "workflow_gen.json"),  
        "name": "✨ Генерация (Old Gen)", 
        "need_photo": False
    },
    "flux_new": {
        "file": os.path.join(BASE_DIR, "TI2I_Flux2_Klein.json"),
        "name": "🚀 Flux Klein Pro",
        "need_photo": False
    }
}

# Хранилище данных пользователя
user_data = {}

if not BOT_TOKEN:
    print("❌ ОШИБКА: TG_TOKEN не задан!")
    sys.exit(1)

# ==========================================
# 🛠 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================

def get_user_data(uid):
    if uid not in user_data:
        user_data[uid] = {
            'image': None,      # Последнее загруженное фото
            'mode': 'flux_new', # Текущий режим
            'batch': 1,
            'msg_ids': []
        }
    return user_data[uid]

async def check_auth(update: Update):
    if not ALLOWED_USERS: return True
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ Этот бот приватный.")
        return False
    return True

# Поиск ID ноды по типу класса (для старых режимов, где ID могут плавать)
def find_node_id(workflow, class_type_list):
    if isinstance(workflow, dict):
        for node_id, node_data in workflow.items():
            if node_data.get("class_type") in class_type_list:
                return node_id
    return None

# --- API COMFYUI ---
def upload_image(file_bytes, file_name):
    """Загружает фото в папку input ComfyUI"""
    try:
        files = {'image': (file_name, file_bytes)}
        data = {'type': 'input', 'overwrite': 'true'}
        response = requests.post(f"http://{COMFY_SERVER}/upload/image", files=files, data=data)
        return response.json()
    except Exception as e:
        print(f"Upload Error: {e}")
        return None

def queue_prompt(prompt_workflow):
    """Отправляет задачу в очередь"""
    p = {"prompt": prompt_workflow, "client_id": CLIENT_ID}
    data = json.dumps(p).encode('utf-8')
    try:
        req = urllib.request.Request(f"http://{COMFY_SERVER}/prompt", data=data)
        return json.loads(urllib.request.urlopen(req).read())
    except Exception as e:
        return {'error': str(e)}

def get_history(prompt_id):
    """Получает историю генерации"""
    try:
        with urllib.request.urlopen(f"http://{COMFY_SERVER}/history/{prompt_id}") as response:
            return json.loads(response.read())
    except: return {}

# ==========================================
# 🎮 ХЕНДЛЕРЫ
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    uid = update.effective_user.id
    user = get_user_data(uid)
    
    # Клавиатура
    kb = [
        [KeyboardButton("🎛 ОТКРЫТЬ ПУЛЬТ (Flux)", web_app=WebAppInfo(url=WEBAPP_URL))],
        [KeyboardButton("🚀 ГЕНЕРАЦИЯ (Old)"), KeyboardButton("🗑 ОЧИСТИТЬ")],
        [KeyboardButton(f"🔄 Режим: {WORKFLOWS[user['mode']]['name']}")],
    ]
    markup = ReplyKeyboardMarkup(kb, resize_keyboard=True)
    
    await update.message.reply_text(
        f"🤖 **NeuroGraph Bot v6.0**\n"
        f"🆔 Pod ID: `{RUNPOD_ID}`\n"
        f"Текущий режим: **{WORKFLOWS[user['mode']]['name']}**\n\n"
        f"👉 Для Flux используй кнопку **'ОТКРЫТЬ ПУЛЬТ'**.\n"
        f"👉 Для старых режимов — кидай фото и жми **'ГЕНЕРАЦИЯ (Old)'**.",
        reply_markup=markup, parse_mode="Markdown"
    )

# --- ОБРАБОТКА ФОТО (Для старых режимов и референсов) ---
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    uid = update.effective_user.id
    user = get_user_data(uid)
    
    msg = await update.message.reply_text("📥 Загружаю фото...")
    try:
        photo_file = await update.message.photo[-1].get_file()
        # Генерируем уникальное имя файла
        fname = f"user_{uid}_{int(time.time())}.jpg"
        file_bytes = await photo_file.download_as_bytearray()
        
        resp = upload_image(file_bytes, fname)
        
        if resp:
            real_name = resp.get("name", fname)
            user['image'] = real_name # Запоминаем для старых режимов
            await msg.edit_text(
                f"✅ Фото сохранено: `{real_name}`\n"
                f"Теперь оно доступно:\n"
                f"1. В меню WebApp (раздел Reference Images)\n"
                f"2. В старом режиме (кнопка Генерация)",
                parse_mode="Markdown"
            )
        else:
            await msg.edit_text("❌ Ошибка загрузки в ComfyUI.")
            
    except Exception as e:
        await msg.edit_text(f"Ошибка бота: {e}")

# --- ОБРАБОТЧИК WEBAPP (НОВЫЙ FLUX) ---
async def handle_webapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    uid = update.effective_user.id
    
    try:
        # 1. Получаем данные от интерфейса
        data = json.loads(update.effective_message.web_app_data.data)
        
        # 2. Грузим новый JSON для Flux
        wf_path = WORKFLOWS["flux_new"]["file"]
        if not os.path.exists(wf_path):
            await update.message.reply_text("❌ Файл TI2I_Flux2_Klein.json не найден!")
            return

        with open(wf_path, "r", encoding="utf-8") as f: wf = json.load(f)

        # === 3. ВСТАВЛЯЕМ ДАННЫЕ (ПО ID ИЗ ТВОЕГО JSON) ===
        
        # Модель (Checkpoint)
        if "116:129" in wf: wf["116:129"]["inputs"]["model_name"] = data["checkpoint"]
        elif "116" in wf: wf["116"]["inputs"]["model_name"] = data["checkpoint"]

        # Разрешение (Resolution Node)
        if "101" in wf: wf["101"]["inputs"]["aspect_ratio"] = data["resolution"]

        # Seed
        seed_val = int(data["seed"]) if int(data["seed"]) != -1 else random.randint(1, 10**15)
        if "117" in wf: wf["117"]["inputs"]["seed"] = seed_val

        # Steps (mxSlider)
        if "119" in wf:
            wf["119"]["inputs"]["Xi"] = int(data["steps"])
            wf["119"]["inputs"]["Xf"] = int(data["steps"])

        # CFG (mxSlider)
        if "118" in wf:
            wf["118"]["inputs"]["Xi"] = float(data["cfg"])
            wf["118"]["inputs"]["Xf"] = float(data["cfg"])

        # Промпты
        if "161" in wf: wf["161"]["inputs"]["value"] = data["prompt_pos"]
        if "162" in wf: wf["162"]["inputs"]["value"] = data["prompt_neg"]

        # Камера (Primitive Nodes)
        if "146" in wf: wf["146"]["inputs"]["value"] = int(data["cam_rot"])
        if "144" in wf: wf["144"]["inputs"]["value"] = int(data["cam_ang"])
        if "151" in wf: wf["151"]["inputs"]["value"] = int(data["cam_dist"])

        # Inpaint
        if "228" in wf: wf["228"]["inputs"]["Xi"] = float(data["ctx"]); wf["228"]["inputs"]["Xf"] = float(data["ctx"])
        if "229" in wf: wf["229"]["inputs"]["Xi"] = float(data["rescale"]); wf["229"]["inputs"]["Xf"] = float(data["rescale"])

        # Reference Images
        # Main Image (Слот 1)
        if "76" in wf and data.get("img1"): 
            wf["76"]["inputs"]["image"] = data["img1"]
        
        # Image 2 + Switch
        if "104" in wf and data.get("img2"): 
            wf["104"]["inputs"]["image"] = data["img2"]
        if "213:214" in wf: wf["213:214"]["inputs"]["value"] = data["img2_on"]
        elif "213" in wf: wf["213"]["inputs"]["value"] = data["img2_on"]

        # Image 3 + Switch
        if "105" in wf and data.get("img3"): 
            wf["105"]["inputs"]["image"] = data["img3"]
        if "214:214" in wf: wf["214:214"]["inputs"]["value"] = data["img3_on"]
        elif "214" in wf: wf["214"]["inputs"]["value"] = data["img3_on"]

        # Reference Scaling
        if "139" in wf: 
            wf["139"]["inputs"]["Xi"] = float(data["ref_scale"])
            wf["139"]["inputs"]["Xf"] = float(data["ref_scale"])

        # LoRA Stacker (Dynamic)
        if "153" in wf:
            loras = data.get("loras", [])
            # Сбрасываем все 13 слотов
            for i in range(1, 14):
                k = f"lora_{i}"
                if k in wf["153"]["inputs"]: wf["153"]["inputs"][k] = {"on": False}
            # Заполняем выбранные
            for i, l in enumerate(loras):
                k = f"lora_{i+1}"
                if k in wf["153"]["inputs"]:
                    wf["153"]["inputs"][k] = {"on": True, "lora": l["name"], "strength": l["weight"]}

        # === ЗАПУСК ГЕНЕРАЦИИ ===
        status = await update.message.reply_text(f"🎬 **Flux Pro** запущен!\nРазрешение: {data['resolution']}")
        
        res = queue_prompt(wf)
        if 'error' in res:
            await status.edit_text(f"❌ Ошибка ComfyUI: {res['error']}")
            return

        # Запускаем мониторинг в фоне
        asyncio.create_task(monitor_generation(context, uid, res['prompt_id'], 1, time.time(), status))

    except Exception as e:
        await update.message.reply_text(f"🔥 Ошибка WebApp: {e}")
        traceback.print_exc()

# --- ОБРАБОТЧИК ТЕКСТА (СТАРЫЕ РЕЖИМЫ) ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    text = update.message.text
    uid = update.effective_user.id
    user = get_user_data(uid)

    if text == "🗑 ОЧИСТИТЬ":
        await update.message.reply_text("История очищена.")

    elif "Режим:" in text:
        # Циклическое переключение
        modes = list(WORKFLOWS.keys())
        idx = modes.index(user['mode'])
        user['mode'] = modes[(idx + 1) % len(modes)]
        await start(update, context) # Обновляем клавиатуру

    elif text == "🚀 ГЕНЕРАЦИЯ (Old)":
        # 1. Проверяем режим
        if user['mode'] == 'flux_new':
            await update.message.reply_text("⚠️ В режиме Flux используйте кнопку **'ОТКРЫТЬ ПУЛЬТ'**!")
            return
            
        cfg = WORKFLOWS[user['mode']]
        
        # 2. Проверяем фото
        if cfg['need_photo'] and not user['image']:
            await update.message.reply_text("⚠️ Для этого режима нужно загрузить фото в чат!")
            return

        # 3. Грузим старый JSON
        if not os.path.exists(cfg['file']):
            await update.message.reply_text(f"❌ Файл {cfg['file']} не найден.")
            return
            
        with open(cfg['file'], "r", encoding="utf-8") as f: wf = json.load(f)

        # 4. ВСТАВЛЯЕМ ДАННЫЕ (Старый метод поиска)
        # Фото
        if cfg['need_photo']:
            load_node = find_node_id(wf, ["LoadImage", "LoadImageMask"])
            if load_node:
                wf[load_node]["inputs"]["image"] = user['image']
        
        # Seed (Рандом)
        seed_node = find_node_id(wf, ["EasySeed", "Seed", "KSampler", "KSamplerAdvanced"])
        if seed_node:
             if "seed" in wf[seed_node]["inputs"]: wf[seed_node]["inputs"]["seed"] = random.randint(1, 10**15)
             elif "noise_seed" in wf[seed_node]["inputs"]: wf[seed_node]["inputs"]["noise_seed"] = random.randint(1, 10**15)

        # 5. Запуск
        msg = await update.message.reply_text(f"🚀 Запускаю **{cfg['name']}**...")
        res = queue_prompt(wf)
        
        if 'error' in res:
            await msg.edit_text(f"❌ Ошибка: {res['error']}")
        else:
            asyncio.create_task(monitor_generation(context, uid, res['prompt_id'], 1, time.time(), msg))

# --- ФУНКЦИЯ ОЖИДАНИЯ РЕЗУЛЬТАТА ---
async def monitor_generation(context, uid, prompt_id, batch, start_ts, status_msg):
    try:
        while True:
            history = get_history(prompt_id)
            if prompt_id in history: break
            await asyncio.sleep(1)

        out = history[prompt_id]['outputs']
        found = False
        
        for nid in out:
            if 'images' in out[nid]:
                for img in out[nid]['images']:
                    # Скачиваем результат
                    url = f"http://{COMFY_SERVER}/view?filename={img['filename']}&subfolder={img['subfolder']}&type={img['type']}"
                    img_data = urllib.request.urlopen(url).read()
                    
                    await context.bot.send_photo(
                        uid, photo=img_data,
                        caption=f"✅ Готово! ({(time.time() - start_ts):.1f}s)"
                    )
                    found = True
        
        if not found: await status_msg.edit_text("⚠️ Пустой результат.")
        else: await status_msg.delete()

    except Exception as e:
        await context.bot.send_message(uid, f"Ошибка при получении результата: {e}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
    print(f"✅ Bot Started on {RUNPOD_ID}")
    app.run_polling()