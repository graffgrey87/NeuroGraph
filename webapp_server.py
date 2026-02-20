from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

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

# === ПУТИ К МОДЕЛЯМ ===
MODELS_DIR = "/workspace/ComfyUI/models"
PATHS = {
    "checkpoints": os.path.join(MODELS_DIR, "diffusion_models"),
    "clip": os.path.join(MODELS_DIR, "text_encoders"), # Или "clip", проверь как у тебя
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

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

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
