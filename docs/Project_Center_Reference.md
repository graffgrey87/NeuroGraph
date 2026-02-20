=== REFERENCE CODEBASE: BOT v5.3 ===



import websocket, uuid, json, urllib.request, urllib.parse, requests, random, os, time, traceback, re, sys, html

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup

from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters



\# ==========================================

\# ⚙️ НАСТРОЙКИ (v5.3 Real Prompt)

\# ==========================================

BOT\_TOKEN = os.getenv("TG\_TOKEN")

raw\_ids = os.getenv("ADMIN\_ID")

ALLOWED\_USERS = \[int(x) for x in raw\_ids.split(",") if x.strip().isdigit()] if raw\_ids else \[]



COMFY\_PORT = "3000"

RUNPOD\_ID = os.environ.get("RUNPOD\_POD\_ID", "127.0.0.1")

COMFY\_SERVER = f"127.0.0.1:{COMFY\_PORT}"

BASE\_DIR = "/workspace"

CLIENT\_ID = str(uuid.uuid4())



\# Настройки режимов

WORKFLOWS = {

&nbsp;   "edit": {

&nbsp;       "file": os.path.join(BASE\_DIR, "workflow\_api.json"), 

&nbsp;       "name": "🎨 Редакт (Qwen)", 

&nbsp;       "need\_photo": True

&nbsp;   },

&nbsp;   "gen": {

&nbsp;       "file": os.path.join(BASE\_DIR, "workflow\_gen.json"),  

&nbsp;       "name": "✨ Генерация (Flux)", 

&nbsp;       "need\_photo": False

&nbsp;   }

}



PROMPT\_NORMAL = "На фото крупным планом показана высокая девушка с изображения 1 которая \_\_действие\_\_ \_\_место\_\_. На ней \_\_наряд\_\_. Её наряд выполнен в \_\_цвет\_\_. Из украшений на ней \_\_украшения\_\_. Ракурс \_\_ракурс\_\_, \_\_угол\_\_, \_\_крупность\_\_ \_\_выражения\_\_. Фото в стиле \_\_стиль\_\_, реалистичное освещение."

PROMPT\_NSFW = "На фото крупным планом показана высокая девушка с изображения 1, которая \_\_действие\_nsfw\_\_ \_\_место\_\_. На ней \_\_наряд\_nsfw\_\_. Она \_\_доп\_действие\_nsfw\_\_. Её наряд выполнен в \_\_цвет\_\_. Из украшений на ней \_\_украшения\_\_. Ракурс \_\_ракурс\_\_, \_\_угол\_\_, \_\_крупность\_\_ \_\_выражения\_\_. Фото в стиле \_\_стиль\_\_, реалистичное освещение."



user\_data = {}



if not BOT\_TOKEN:

&nbsp;   print("❌ ОШИБКА: TG\_TOKEN не задан!")

&nbsp;   sys.exit(1)



\# ==========================================

\# 🛠 ПОМОЩНИКИ

\# ==========================================

def escape\_html(text):

&nbsp;   """Экранирует символы для HTML (чтобы бот не падал)"""

&nbsp;   return html.escape(str(text))



async def check\_auth(update: Update):

&nbsp;   if update.effective\_user.id not in ALLOWED\_USERS:

&nbsp;       await update.message.reply\_text("⛔ Доступ запрещен.")

&nbsp;       return False

&nbsp;   return True



def get\_user\_data(uid):

&nbsp;   if uid not in user\_data:

&nbsp;       user\_data\[uid] = {

&nbsp;           'image': None, 

&nbsp;           'mode': 'normal', 

&nbsp;           'wf': 'edit', 

&nbsp;           'batch': 1, 

&nbsp;           'dataset\_name': 'Batch', 

&nbsp;           'msg\_ids': \[],

&nbsp;           'loras': {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}, 

&nbsp;           'awaiting\_lora': None,

&nbsp;           'awaiting\_custom\_batch': False,

&nbsp;           'awaiting\_dataset\_name': False

&nbsp;       }

&nbsp;   return user\_data\[uid]



def track\_message(user\_id, message\_id):

&nbsp;   """Сохраняет ID для очистки"""

&nbsp;   data = get\_user\_data(user\_id)

&nbsp;   if message\_id not in data\['msg\_ids']:

&nbsp;       data\['msg\_ids'].append(message\_id)

&nbsp;   if len(data\['msg\_ids']) > 100: 

&nbsp;       data\['msg\_ids'].pop(0)



def fix\_paths\_for\_linux(workflow):

&nbsp;   """Меняет \\ на / (Linux Fix)"""

&nbsp;   for nid, node in workflow.items():

&nbsp;       if "inputs" in node:

&nbsp;           for key, val in node\["inputs"].items():

&nbsp;               if isinstance(val, str) and "\\\\" in val:

&nbsp;                   node\["inputs"]\[key] = val.replace("\\\\", "/")

&nbsp;   return workflow



def find\_node\_id(workflow, class\_type\_list):

&nbsp;   if isinstance(workflow, dict):

&nbsp;       for node\_id, node\_data in workflow.items():

&nbsp;           if node\_data.get("class\_type") in class\_type\_list: return node\_id

&nbsp;   return None



\# --- 🔥 ПАРСЕР ИМЕН ЛОР ---

def get\_lora\_names(uid):

&nbsp;   names = {1: "LORA 1", 2: "LORA 2", 3: "LORA 3", 4: "LORA 4"}

&nbsp;   data = get\_user\_data(uid)

&nbsp;   current\_mode = data\['wf']

&nbsp;   

&nbsp;   if current\_mode not in WORKFLOWS: return names

&nbsp;   target\_file = WORKFLOWS\[current\_mode]\['file']

&nbsp;   

&nbsp;   if not os.path.exists(target\_file): return names



&nbsp;   try:

&nbsp;       with open(target\_file, "r", encoding="utf-8") as f:

&nbsp;           wf = json.load(f)

&nbsp;       

&nbsp;       nid = find\_node\_id(wf, \["Power Lora Loader (rgthree)"])

&nbsp;       if nid:

&nbsp;           inputs = wf\[nid]\["inputs"]

&nbsp;           for i in range(1, 5):

&nbsp;               key = f"lora\_{i}"

&nbsp;               if key in inputs and "lora" in inputs\[key]:

&nbsp;                   raw = inputs\[key]\["lora"]

&nbsp;                   clean = raw.replace("\\\\", "/").split("/")\[-1]

&nbsp;                   clean = clean.replace(".safetensors", "")

&nbsp;                   clean = clean.replace("\_", " ").replace("-", " ")

&nbsp;                   if len(clean) > 20: clean = clean\[:18] + ".."

&nbsp;                   names\[i] = clean

&nbsp;   except Exception as e:

&nbsp;       print(f"❌ Ошибка имен: {e}")

&nbsp;       

&nbsp;   return names



\# --- API COMFYUI ---

def upload\_image(file\_bytes, file\_name):

&nbsp;   try:

&nbsp;       files = {'image': (file\_name, file\_bytes)}

&nbsp;       data = {'type': 'input', 'overwrite': 'true'}

&nbsp;       response = requests.post(f"http://{COMFY\_SERVER}/upload/image", files=files, data=data)

&nbsp;       return response.json()

&nbsp;   except: return None



def queue\_prompt(prompt\_workflow):

&nbsp;   p = {"prompt": prompt\_workflow, "client\_id": CLIENT\_ID}

&nbsp;   data = json.dumps(p).encode('utf-8')

&nbsp;   req = urllib.request.Request(f"http://{COMFY\_SERVER}/prompt", data=data)

&nbsp;   return json.loads(urllib.request.urlopen(req).read())



def get\_history(prompt\_id):

&nbsp;   try:

&nbsp;       with urllib.request.urlopen(f"http://{COMFY\_SERVER}/history/{prompt\_id}") as response:

&nbsp;           return json.loads(response.read())

&nbsp;   except: return {}



def get\_view(filename, subfolder, folder\_type):

&nbsp;   data = {"filename": filename, "subfolder": subfolder, "type": folder\_type}

&nbsp;   url\_values = urllib.parse.urlencode(data)

&nbsp;   with urllib.request.urlopen(f"http://{COMFY\_SERVER}/view?{url\_values}") as response:

&nbsp;       return response.read()



\# --- КЛАВИАТУРЫ ---

def get\_main\_kb(uid):

&nbsp;   d = get\_user\_data(uid)

&nbsp;   wf\_name = WORKFLOWS\[d\['wf']]\['name']

&nbsp;   mode\_icon = "😇" if d\['mode'] == 'normal' else "😈"

&nbsp;   kb = \[

&nbsp;       \[KeyboardButton("🚀 ГЕНЕРАЦИЯ"), KeyboardButton("🗑 ОЧИСТИТЬ")],

&nbsp;       \[KeyboardButton(f"🔄 WF: {wf\_name}"), KeyboardButton(f"🔢 Кол-во: {d\['batch']}")],

&nbsp;       \[KeyboardButton(f"{mode\_icon} Режим: {d\['mode'].upper()}"), KeyboardButton("🎛 LORA MIXER")],

&nbsp;       \[KeyboardButton(f"🏷 Имя сета: {d\['dataset\_name']}"), KeyboardButton("🌐 Ссылки \& WebUI")]

&nbsp;   ]

&nbsp;   return ReplyKeyboardMarkup(kb, resize\_keyboard=True)



def get\_lora\_kb(uid):

&nbsp;   d = get\_user\_data(uid)

&nbsp;   real\_names = get\_lora\_names(uid)

&nbsp;   kb = \[]

&nbsp;   for i in range(1, 5):

&nbsp;       val = d\['loras'].get(i, 0.0)

&nbsp;       status = f"✅ {val}" if val > 0 else "❌ OFF"

&nbsp;       name = real\_names\[i]

&nbsp;       kb.append(\[InlineKeyboardButton(f"{i}. {name} | {status}", callback\_data=f"edit\_lora\_{i}")])

&nbsp;   kb.append(\[InlineKeyboardButton("🔙 Закрыть меню", callback\_data="close\_lora")])

&nbsp;   return InlineKeyboardMarkup(kb)



def get\_links\_kb():

&nbsp;   base = f"https://{RUNPOD\_ID}"

&nbsp;   url\_comfy = f"{base}-{COMFY\_PORT}.proxy.runpod.net/"

&nbsp;   url\_gallery = f"{base}-8083.proxy.runpod.net/"

&nbsp;   url\_down = f"{base}-8081.proxy.runpod.net/"

&nbsp;   url\_civit = f"{base}-8082.proxy.runpod.net/"

&nbsp;   url\_jupyter = f"{base}-8888.proxy.runpod.net/"

&nbsp;   

&nbsp;   kb = \[

&nbsp;       \[InlineKeyboardButton("🎨 ComfyUI Web (3000)", url=url\_comfy)],

&nbsp;       \[InlineKeyboardButton("🖼 Галерея (8083)", url=url\_gallery), InlineKeyboardButton("💾 Files (8081)", url=url\_down)],

&nbsp;       \[InlineKeyboardButton("🧠 CivitAI (8082)", url=url\_civit), InlineKeyboardButton("📂 Jupyter (8888)", url=url\_jupyter)],

&nbsp;       \[InlineKeyboardButton("❌ Закрыть", callback\_data="close\_links")]

&nbsp;   ]

&nbsp;   return InlineKeyboardMarkup(kb)



def get\_batch\_kb():

&nbsp;   kb = \[

&nbsp;       \[InlineKeyboardButton("1", callback\_data="batch\_1"), InlineKeyboardButton("2", callback\_data="batch\_2"), InlineKeyboardButton("3", callback\_data="batch\_3")],

&nbsp;       \[InlineKeyboardButton("5", callback\_data="batch\_5"), InlineKeyboardButton("10", callback\_data="batch\_10")],

&nbsp;       \[InlineKeyboardButton("⌨️ Свое число", callback\_data="batch\_custom")]

&nbsp;   ]

&nbsp;   return InlineKeyboardMarkup(kb)



\# --- ОБРАБОТЧИКИ ---

async def start(update: Update, context: ContextTypes.DEFAULT\_TYPE):

&nbsp;   if not await check\_auth(update): return

&nbsp;   uid = update.effective\_user.id

&nbsp;   msg = await update.message.reply\_text(f"🎛 \*\*NeuroGraph v5.3\*\*\\nID: `{RUNPOD\_ID}`", reply\_markup=get\_main\_kb(uid), parse\_mode="Markdown")

&nbsp;   track\_message(uid, update.message.message\_id)

&nbsp;   track\_message(uid, msg.message\_id)



async def handle\_photo(update: Update, context: ContextTypes.DEFAULT\_TYPE):

&nbsp;   if not await check\_auth(update): return

&nbsp;   uid = update.effective\_user.id

&nbsp;   track\_message(uid, update.message.message\_id)

&nbsp;   msg = await update.message.reply\_text("📥 Загрузка...")

&nbsp;   track\_message(uid, msg.message\_id)

&nbsp;   try:

&nbsp;       photo = await update.message.photo\[-1].get\_file()

&nbsp;       fname = f"user\_{uid}\_{uuid.uuid4().hex\[:4]}.jpg"

&nbsp;       fbytes = await photo.download\_as\_bytearray()

&nbsp;       resp = upload\_image(fbytes, fname)

&nbsp;       if resp:

&nbsp;           real\_name = resp.get("name", fname)

&nbsp;           get\_user\_data(uid)\['image'] = real\_name

&nbsp;           await msg.edit\_text(f"✅ Фото принято: `{real\_name}`", parse\_mode="Markdown")

&nbsp;       else: await msg.edit\_text("❌ Ошибка загрузки.")

&nbsp;   except Exception as e: await msg.edit\_text(f"Ошибка: {e}")



async def handle\_callback(update: Update, context: ContextTypes.DEFAULT\_TYPE):

&nbsp;   query = update.callback\_query

&nbsp;   uid = query.from\_user.id

&nbsp;   d = get\_user\_data(uid)

&nbsp;   await query.answer()



&nbsp;   if query.data.startswith("batch\_"):

&nbsp;       if query.data == "batch\_custom":

&nbsp;           d\['awaiting\_custom\_batch'] = True

&nbsp;           await query.message.edit\_text("⌨️ \*\*Введите число\*\* (например 50):", parse\_mode="Markdown")

&nbsp;       else:

&nbsp;           count = int(query.data.split("\_")\[1])

&nbsp;           d\['batch'] = count

&nbsp;           await query.message.edit\_text(f"🔢 Batch: \*\*{count}\*\*", parse\_mode="Markdown")

&nbsp;           m = await context.bot.send\_message(chat\_id=uid, text="Меню обновлено", reply\_markup=get\_main\_kb(uid))

&nbsp;           track\_message(uid, m.message\_id)



&nbsp;   elif query.data.startswith("edit\_lora\_"):

&nbsp;       slot = int(query.data.split("\_")\[2])

&nbsp;       d\['awaiting\_lora'] = slot

&nbsp;       names = get\_lora\_names(uid)

&nbsp;       await query.message.edit\_text(f"✍️ \*\*{names\[slot]}\*\*\\nВведите вес (0.1 - 1.0) или 0:", parse\_mode="Markdown")

&nbsp;   

&nbsp;   elif query.data == "close\_lora" or query.data == "close\_links":

&nbsp;       await query.message.delete()



async def handle\_msg(update: Update, context: ContextTypes.DEFAULT\_TYPE):

&nbsp;   if not await check\_auth(update): return

&nbsp;   uid = update.effective\_user.id

&nbsp;   text = update.message.text

&nbsp;   d = get\_user\_data(uid)

&nbsp;   track\_message(uid, update.message.message\_id)



&nbsp;   # 1. BATCH CUSTOM

&nbsp;   if d.get('awaiting\_custom\_batch'):

&nbsp;       if text.isdigit():

&nbsp;           val = int(text)

&nbsp;           d\['batch'] = val

&nbsp;           d\['awaiting\_custom\_batch'] = False

&nbsp;           m = await update.message.reply\_text(f"🔢 Установлен Batch: \*\*{val}\*\*", reply\_markup=get\_main\_kb(uid), parse\_mode="Markdown")

&nbsp;           track\_message(uid, m.message\_id)

&nbsp;       else:

&nbsp;           m = await update.message.reply\_text("⚠️ Введите целое число!")

&nbsp;           track\_message(uid, m.message\_id)

&nbsp;       return



&nbsp;   # 2. DATASET NAME

&nbsp;   if d.get('awaiting\_dataset\_name'):

&nbsp;       d\['dataset\_name'] = text

&nbsp;       d\['awaiting\_dataset\_name'] = False

&nbsp;       m = await update.message.reply\_text(f"🏷 Имя сета: \*\*{text}\*\*", reply\_markup=get\_main\_kb(uid), parse\_mode="Markdown")

&nbsp;       track\_message(uid, m.message\_id)

&nbsp;       return



&nbsp;   # 3. LORA WEIGHT

&nbsp;   if d\['awaiting\_lora']:

&nbsp;       try:

&nbsp;           val = float(text.replace(",", "."))

&nbsp;           slot = d\['awaiting\_lora']

&nbsp;           d\['loras']\[slot] = val

&nbsp;           d\['awaiting\_lora'] = None

&nbsp;           names = get\_lora\_names(uid)

&nbsp;           m1 = await update.message.reply\_text(f"✅ {names\[slot]} -> {val}", reply\_markup=get\_main\_kb(uid))

&nbsp;           track\_message(uid, m1.message\_id)

&nbsp;           m2 = await update.message.reply\_text("🎛 Микшер:", reply\_markup=get\_lora\_kb(uid))

&nbsp;           track\_message(uid, m2.message\_id)

&nbsp;           return

&nbsp;       except:

&nbsp;           m = await update.message.reply\_text("⚠️ Введите число")

&nbsp;           track\_message(uid, m.message\_id)

&nbsp;           return



&nbsp;   # 4. CLEAN

&nbsp;   if text == "🗑 ОЧИСТИТЬ":

&nbsp;       count = 0

&nbsp;       for mid in reversed(d\['msg\_ids']):

&nbsp;           try: 

&nbsp;               await context.bot.delete\_message(chat\_id=uid, message\_id=mid)

&nbsp;               count += 1

&nbsp;           except: pass

&nbsp;       d\['msg\_ids'] = \[]

&nbsp;       clean\_msg = await update.message.reply\_text(f"🧹 Чисто ({count} удалено).", reply\_markup=get\_main\_kb(uid))

&nbsp;       track\_message(uid, clean\_msg.message\_id)



&nbsp;   # 5. MENUS

&nbsp;   elif text == "🎛 LORA MIXER":

&nbsp;       m = await update.message.reply\_text("🎛 Настройка Лор:", reply\_markup=get\_lora\_kb(uid))

&nbsp;       track\_message(uid, m.message\_id)



&nbsp;   elif text == "🌐 Ссылки \& WebUI":

&nbsp;       m = await update.message.reply\_text("🔗 Порты:", reply\_markup=get\_links\_kb())

&nbsp;       track\_message(uid, m.message\_id)

&nbsp;   

&nbsp;   elif text.startswith("🔢"):

&nbsp;       m = await update.message.reply\_text("Количество:", reply\_markup=get\_batch\_kb())

&nbsp;       track\_message(uid, m.message\_id)

&nbsp;   

&nbsp;   elif text.startswith("🏷"):

&nbsp;       d\['awaiting\_dataset\_name'] = True

&nbsp;       m = await update.message.reply\_text("📝 Введите новое имя для файлов (префикс):")

&nbsp;       track\_message(uid, m.message\_id)

&nbsp;   

&nbsp;   elif text.startswith("🔄"):

&nbsp;       keys = list(WORKFLOWS.keys())

&nbsp;       idx = keys.index(d\['wf'])

&nbsp;       d\['wf'] = keys\[(idx + 1) % len(keys)]

&nbsp;       m = await update.message.reply\_text(f"🔄 Режим: \*\*{WORKFLOWS\[d\['wf']]\['name']}\*\*", reply\_markup=get\_main\_kb(uid), parse\_mode="Markdown")

&nbsp;       track\_message(uid, m.message\_id)

&nbsp;   

&nbsp;   elif "Режим:" in text:

&nbsp;       d\['mode'] = 'nsfw' if d\['mode'] == 'normal' else 'normal'

&nbsp;       m = await update.message.reply\_text(f"Режим: {d\['mode'].upper()}", reply\_markup=get\_main\_kb(uid))

&nbsp;       track\_message(uid, m.message\_id)

&nbsp;   

&nbsp;   elif text == "🚀 ГЕНЕРАЦИЯ":

&nbsp;       await run\_generation(update, context, uid)

&nbsp;   

&nbsp;   else:

&nbsp;       await run\_generation(update, context, uid, manual\_prompt=text)



async def run\_generation(update, context, uid, manual\_prompt=None):

&nbsp;   d = get\_user\_data(uid)

&nbsp;   cfg = WORKFLOWS\[d\['wf']]

&nbsp;   

&nbsp;   if cfg\['need\_photo'] and not d\['image']:

&nbsp;       m = await update.message.reply\_text(f"⚠️ Нужно фото!")

&nbsp;       track\_message(uid, m.message\_id)

&nbsp;       return



&nbsp;   prompt\_txt = manual\_prompt if manual\_prompt else (PROMPT\_NORMAL if d\['mode'] == 'normal' else PROMPT\_NSFW)

&nbsp;   

&nbsp;   status\_msg = await update.message.reply\_text(f"🚀 Запуск {d\['batch']} шт...\\n📂 Set: {d\['dataset\_name']}")

&nbsp;   track\_message(uid, status\_msg.message\_id)



&nbsp;   for i in range(d\['batch']):

&nbsp;       start\_ts = time.time()

&nbsp;       try:

&nbsp;           if not os.path.exists(cfg\['file']):

&nbsp;               await context.bot.send\_message(uid, f"❌ Нет файла: {cfg\['file']}")

&nbsp;               break

&nbsp;           

&nbsp;           with open(cfg\['file'], "r", encoding="utf-8") as f: wf = json.load(f)



&nbsp;           # === AUTO-FIX ===

&nbsp;           wf = fix\_paths\_for\_linux(wf)



&nbsp;           # === SET NAME (Node 211) ===

&nbsp;           if "211" in wf and "inputs" in wf\["211"]:

&nbsp;               wf\["211"]\["inputs"]\["value"] = d\['dataset\_name']



&nbsp;           # === LORA MIXER ===

&nbsp;           lid = find\_node\_id(wf, \["Power Lora Loader (rgthree)"])

&nbsp;           if lid:

&nbsp;               for s in range(1, 5):

&nbsp;                   k = f"lora\_{s}"

&nbsp;                   if k in wf\[lid]\["inputs"]:

&nbsp;                       v = d\['loras'].get(s, 0.0)

&nbsp;                       wf\[lid]\["inputs"]\[k]\["strength"] = v

&nbsp;                       wf\[lid]\["inputs"]\[k]\["on"] = (v > 0)



&nbsp;           # === SEED ===

&nbsp;           sid = find\_node\_id(wf, \["easy seed", "EasySeed"])

&nbsp;           if sid: wf\[sid]\["inputs"]\["seed"] = random.randint(1, 10\*\*15)

&nbsp;           else:

&nbsp;               sid = find\_node\_id(wf, \["Seed", "KSampler"])

&nbsp;               if sid: wf\[sid]\["inputs"]\["seed"] = random.randint(1, 10\*\*15)



&nbsp;           # === PROMPT \& IMAGE ===

&nbsp;           iid = find\_node\_id(wf, \["LoadImage"])

&nbsp;           tid = find\_node\_id(wf, \["String Literal", "CLIPTextEncode", "PrimitiveString"])

&nbsp;           

&nbsp;           if iid and cfg\['need\_photo']: wf\[iid]\["inputs"]\["image"] = d\['image']

&nbsp;           if tid:

&nbsp;               tkey = "string" if "string" in wf\[tid]\["inputs"] else "text"

&nbsp;               wf\[tid]\["inputs"]\[tkey] = prompt\_txt



&nbsp;           res = queue\_prompt(wf)

&nbsp;           if 'error' in res:

&nbsp;               await context.bot.send\_message(uid, f"Comfy Error: {res\['error']}")

&nbsp;               break

&nbsp;           

&nbsp;           pid = res\['prompt\_id']

&nbsp;           while True:

&nbsp;               h = get\_history(pid)

&nbsp;               if pid in h: break

&nbsp;               time.sleep(1)

&nbsp;           

&nbsp;           dur = time.time() - start\_ts

&nbsp;           out = h\[pid]\['outputs']

&nbsp;           found = False

&nbsp;           

&nbsp;           # 🔥 ПОИСК РЕАЛЬНОГО ТЕКСТА В ИСТОРИИ (Node 207 и др)

&nbsp;           real\_prompt = prompt\_txt # Значение по умолчанию

&nbsp;           for nid in out:

&nbsp;               if 'text' in out\[nid]:

&nbsp;                   val = out\[nid]\['text']

&nbsp;                   if isinstance(val, list): real\_prompt = " ".join(\[str(x) for x in val])

&nbsp;                   else: real\_prompt = str(val)

&nbsp;                   break # Берем первый найденный текст (обычно это ShowText)



&nbsp;           for nid in out:

&nbsp;               if 'images' in out\[nid]:

&nbsp;                   for img in out\[nid]\['images']:

&nbsp;                       idata = get\_view(img\['filename'], img\['subfolder'], img\['type'])

&nbsp;                       

&nbsp;                       # 🔥 ОТОБРАЖЕНИЕ: Без спойлера, реальный текст, HTML экранирование

&nbsp;                       safe\_prompt = escape\_html(real\_prompt\[:900]) # Обрезаем до 900 символов

&nbsp;                       cap = f"<b>🖼 {i+1}/{d\['batch']} ({dur:.1f}s)</b>\\n\\n{safe\_prompt}"

&nbsp;                       

&nbsp;                       m = await context.bot.send\_photo(uid, idata, caption=cap, parse\_mode="HTML")

&nbsp;                       track\_message(uid, m.message\_id)

&nbsp;                       found = True

&nbsp;           

&nbsp;           if not found:

&nbsp;               m = await context.bot.send\_message(uid, "⚠️ Пусто")

&nbsp;               track\_message(uid, m.message\_id)



&nbsp;       except Exception as e:

&nbsp;           m = await context.bot.send\_message(uid, f"Crash: {e}")

&nbsp;           track\_message(uid, m.message\_id)

&nbsp;           traceback.print\_exc()



&nbsp;   try: await context.bot.delete\_message(uid, status\_msg.message\_id)

&nbsp;   except: pass

&nbsp;   

&nbsp;   fin = await context.bot.send\_message(uid, "🏁 Готово!")

&nbsp;   track\_message(uid, fin.message\_id)



if \_\_name\_\_ == '\_\_main\_\_':

&nbsp;   app = ApplicationBuilder().token(BOT\_TOKEN).build()

&nbsp;   app.add\_handler(CommandHandler('start', start))

&nbsp;   app.add\_handler(MessageHandler(filters.PHOTO, handle\_photo))

&nbsp;   app.add\_handler(CallbackQueryHandler(handle\_callback))

&nbsp;   app.add\_handler(MessageHandler(filters.TEXT \& (~filters.COMMAND), handle\_msg))

&nbsp;   print(f"Bot v5.3 (Real Prompt) Started on {RUNPOD\_ID}")

&nbsp;   app.run\_polling()







=== REFERENCE SCRIPT: INSTALL.SH ===



\#!/bin/bash



\# ПУТИ

VENV\_PYTHON="/workspace/venv/bin/python"

VENV\_PIP="/workspace/venv/bin/pip"

L\_PATH="/workspace/ComfyUI/models/loras"



\# 1. ЖДЕМ ПОРТ 3000

echo "⏳ Жду порт 3000..."

while ! wget -q --spider http://127.0.0.1:3000; do

&nbsp; sleep 2

done

echo "✅ Порт 3000 активен."



\# 2. БИБЛИОТЕКИ

echo "📦 Ставлю библиотеки..."

$VENV\_PIP install python-telegram-bot requests websocket-client > /dev/null 2>\&1



\# 3. НОДЫ

echo "🧩 Ставлю ноды..."

cd /workspace/ComfyUI/custom\_nodes

\[ ! -d "mikey\_nodes" ] \&\& git clone https://github.com/bash-j/mikey\_nodes.git

\[ ! -d "comfy-image-saver" ] \&\& git clone https://github.com/giriss/comfy-image-saver.git

\[ ! -d "ComfyUI-Custom-Scripts" ] \&\& git clone https://github.com/pythongosssss/ComfyUI-Custom-Scripts.git



\# 4. КАЧАЕМ ЛОРЫ (С ПОДРОБНЫМ ЛОГОМ)

echo "⬇️ Качаю Лоры..."

mkdir -p "$L\_PATH"



download\_model() {

&nbsp;   url="$1"

&nbsp;   file="$2"

&nbsp;   echo "---------------------------------------------------"

&nbsp;   echo "📥 Скачиваю: $file"

&nbsp;   

&nbsp;   if \[ -z "$HF\_TOKEN" ]; then

&nbsp;       echo "⚠️ HF\_TOKEN не найден в переменных! Пробую качать без пароля..."

&nbsp;       # Убрал -q, чтобы видеть ошибки

&nbsp;       wget -nc -O "$L\_PATH/$file" "$url"

&nbsp;   else

&nbsp;       echo "🔒 Использую HF\_TOKEN для авторизации..."

&nbsp;       # Убрал -q, добавил хедер

&nbsp;       wget --header "Authorization: Bearer $HF\_TOKEN" -nc -O "$L\_PATH/$file" "$url"

&nbsp;   fi

}



\# Список файлов

download\_model "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/Qwen4Play\_v2.safetensors?download=true" "Qwen4Play\_v2.safetensors"

download\_model "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/Qwen\_Snofs\_1\_3.safetensors?download=true" "Qwen\_Snofs\_1\_3.safetensors"

download\_model "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/breast\_slider\_qwen\_v1.safetensors?download=true" "breast\_slider\_qwen\_v1.safetensors"

download\_model "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/hips\_size\_slider\_v1.safetensors?download=true" "hips\_size\_slider\_v1.safetensors"



echo "---------------------------------------------------"

echo "📂 ИТОГОВАЯ ПРОВЕРКА ПАПКИ (Размер не должен быть 0):"

ls -lh "$L\_PATH"

echo "---------------------------------------------------"



\# 5. КОПИРУЕМ БОТА

echo "🤖 Копирую бота..."

cp /workspace/installer/bot.py /workspace/bot.py

cp /workspace/installer/\*.json /workspace/ 2>/dev/null

\[ -d "/workspace/installer/wildcards" ] \&\& cp -r "/workspace/installer/wildcards" "/workspace/ComfyUI/"



\# 6. ПЕРЕЗАПУСК

echo "🔄 Убиваю процессы..."

pkill -f "python main.py"

pkill -f "bot.py"

sleep 5



echo "🤖 Старт Бота..."

nohup $VENV\_PYTHON /workspace/bot.py > /workspace/bot.log 2>\&1 \&



echo "🚀 Старт ComfyUI..."

cd /workspace/ComfyUI

$VENV\_PYTHON main.py --listen 0.0.0.0 --port 3000





=== ENVIRONMENT \& PORTS ===

Ports:

\- 3000: ComfyUI Backend (API)

\- 8081: Comfy Image Saver / File Browser

\- 8082: CivitAI Helper

\- 8083: Gallery



Variables (.env logic):

\- RUNPOD\_ID: Auto-detected

\- COMFY\_PORT: 3000

\- MODELS\_PATH: /workspace/ComfyUI/models/loras

###### -Container image: smyshnikof/comfyui:base-torch2.8.0-cu128

###### -Container Start Command:

&nbsp;

bash -c "rm -rf /workspace/installer; git clone https://github.com/graffgrey87/NeuroGraph.git /workspace/installer; (while ! curl -s http://localhost:3000 > /dev/null; do sleep 10; done; echo '✅ ComfyUI detected! Waiting 30s...'; sleep 30; bash /workspace/installer/install.sh) \& /start.sh"



###### \-Environment variables:



HF\_TOKEN               



CIVITAI\_API\_TOKEN    



TIME\_ZONE               Etc/UTC



INSTALL\_SAGEATTENTION   True



JUPYTER\_PASSWORD        n0d1esbdqbxkz3f1xnwi



TG\_TOKEN              



ADMIN\_ID                386074947





=== KNOWN ISSUES \& FIXES ===

1\. Проблема: Windows paths ("\\") в JSON воркфлоу ломают загрузку на Linux.

&nbsp;  Решение: Функция fix\_paths\_for\_linux в bot.py обязательна.

2\. Проблема: Telegram падает при отправке символов < > в режиме parse\_mode="HTML".

&nbsp;  Решение: Функция html.escape() для текста промпта.

3\. Проблема: RunPod при перезагрузке очищает pip пакеты.

&nbsp;  Решение: Скрипт install.sh должен запускаться при старте пода.



=== WORKFLOW CONFIGURATION ===

Mapping:

\- "edit": workflow\_api.json (Requires Image Load)

\- "gen": workflow\_gen.json (Text to Image)

Node IDs (Common):

\- Seed: "EasySeed" 

\- Lora Loader: "Power Lora Loader (rgthree)"

\- Text Output: Node 207 or "ShowText"

