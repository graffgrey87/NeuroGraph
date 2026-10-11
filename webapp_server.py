from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import json
from io import BytesIO

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = "/workspace"
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
USER_DATA_FILE = os.path.join(BASE_DIR, "user_data.json")

# === ПУТИ К МОДЕЛЯМ ===
MODELS_DIR = "/workspace/ComfyUI/models"
PATHS = {
    "checkpoints": os.path.join(MODELS_DIR, "diffusion_models"),
    "clip": os.path.join(MODELS_DIR, "text_encoders"),
    "vae": os.path.join(MODELS_DIR, "vae"),
    "loras": os.path.join(MODELS_DIR, "loras"),
    "images": "/workspace/ComfyUI/input"
}

# Создаем папки и шаблоны
for d in [TEMPLATE_DIR, STATIC_DIR]:
    if not os.path.exists(d): os.makedirs(d)

if not os.path.exists(os.path.join(TEMPLATE_DIR, "index.html")):
    with open(os.path.join(TEMPLATE_DIR, "index.html"), "w") as f:
        f.write("<h1>Server Active</h1>")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATE_DIR)

def scan_files(folder, extensions):
    found = []
    if not os.path.exists(folder): return []
    for root, dirs, files in os.walk(folder):
        for file in files:
            if file.lower().endswith(extensions):
                rel_path = os.path.relpath(os.path.join(root, file), folder)
                found.append(rel_path.replace("\\", "/"))
    return sorted(found)

def _load_user_data():
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, "r") as f:
                return json.load(f)
        except: pass
    return {}

def _save_user_data(data):
    try:
        with open(USER_DATA_FILE, "w") as f:
            json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
    except: pass

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/status", response_class=HTMLResponse)
async def status_page(request: Request):
    return templates.TemplateResponse(request=request, name="status.html")

@app.get("/api/system_status")
async def get_system_status():
    import urllib.request
    import urllib.error
    
    comfy_url = "http://127.0.0.1:3000"
    try:
        # Статика (GPU, RAM)
        req_stats = urllib.request.Request(f"{comfy_url}/system_stats")
        with urllib.request.urlopen(req_stats, timeout=2) as res:
            stats = json.loads(res.read())
            
        # Динамика (очередь Pending/Running)
        req_queue = urllib.request.Request(f"{comfy_url}/queue")
        with urllib.request.urlopen(req_queue, timeout=2) as res:
            queue = json.loads(res.read())
            
        return JSONResponse({"status": "online", "stats": stats, "queue": queue})
    except Exception as e:
        return JSONResponse({"status": "offline", "error": str(e)})

# === PRESETS API ===
@app.get("/api/presets")
async def get_presets(uid: str = ""):
    if not uid: return JSONResponse({"presets": {}})
    data = _load_user_data()
    user = data.get(uid, {})
    return JSONResponse({"presets": user.get("presets", {})})

@app.post("/api/presets")
async def save_preset(request: Request):
    body = await request.json()
    uid = str(body.get("uid", ""))
    name = body.get("name", "")
    preset_data = body.get("data", {})
    if not uid or not name:
        return JSONResponse({"error": "uid and name required"}, status_code=400)
    data = _load_user_data()
    if uid not in data: data[uid] = {}
    if "presets" not in data[uid]: data[uid]["presets"] = {}
    data[uid]["presets"][name] = preset_data
    _save_user_data(data)
    return JSONResponse({"ok": True, "presets": data[uid]["presets"]})

@app.delete("/api/presets")
async def delete_preset(uid: str = "", name: str = ""):
    if not uid or not name:
        return JSONResponse({"error": "uid and name required"}, status_code=400)
    data = _load_user_data()
    user = data.get(uid, {})
    presets = user.get("presets", {})
    if name in presets:
        del presets[name]
        _save_user_data(data)
    return JSONResponse({"ok": True, "presets": presets})

# === PREVIEW API ===
@app.get("/api/preview")
async def preview_image(file: str = ""):
    if not file: return JSONResponse({"error": "file required"}, status_code=400)
    filepath = os.path.join(PATHS["images"], file)
    if not os.path.exists(filepath):
        return JSONResponse({"error": "not found"}, status_code=404)
    try:
        from PIL import Image
        img = Image.open(filepath)
        img.thumbnail((150, 150))
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=70)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/jpeg")
    except ImportError:
        return StreamingResponse(open(filepath, "rb"), media_type="image/jpeg")

# === MODEL FILES API ===
@app.get("/api/{type}")
async def get_files(type: str):
    if type == "checkpoints": ext = (".safetensors", ".ckpt")
    elif type == "clip": ext = (".safetensors", ".pt", ".bin")
    elif type == "vae": ext = (".safetensors", ".pt")
    elif type == "loras": ext = (".safetensors", ".pt")
    elif type == "images": ext = (".jpg", ".jpeg", ".png", ".webp")
    else: return JSONResponse({"error": "Unknown type"})
    
    path = PATHS.get(type)
    files = scan_files(path, ext) if path else []
    return JSONResponse(content={type: files})



if __name__ == "__main__":
    print("🚀 Server running on 8099")
    uvicorn.run(app, host="0.0.0.0", port=8099)
