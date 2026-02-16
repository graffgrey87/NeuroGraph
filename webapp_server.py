from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

app = FastAPI()

# Разрешаем CORS
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

# === 📂 ПУТИ К ПАПКАМ ===
# 1. Модели (Flux/Checkpoints)
CHECKPOINT_DIR = "/workspace/ComfyUI/models/diffusion_models"
# 2. Лоры
LORA_DIR = "/workspace/ComfyUI/models/loras"
# 3. Картинки пользователя (для Референсов)
INPUT_DIR = "/workspace/ComfyUI/input"

# Создаем папки если нет
for d in [TEMPLATE_DIR, STATIC_DIR, INPUT_DIR]:
    if not os.path.exists(d): os.makedirs(d)

if not os.path.exists(os.path.join(TEMPLATE_DIR, "index.html")):
    with open(os.path.join(TEMPLATE_DIR, "index.html"), "w") as f:
        f.write("<h1>WebApp Server Active. Waiting for update...</h1>")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATE_DIR)

# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ПОИСКА ---
def scan_files(folder, extensions):
    found = []
    if not os.path.exists(folder): return []
    for root, dirs, files in os.walk(folder):
        for file in files:
            if file.lower().endswith(extensions):
                # Полный путь не нужен, нужен относительный для ComfyUI
                rel_path = os.path.relpath(os.path.join(root, file), folder)
                # Для Windows путей меняем слэши, на Linux и так ок
                found.append(rel_path.replace("\\", "/"))
    return sorted(found)

# === ROUTES ===

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/checkpoints")
async def get_checkpoints():
    # Ищем safetensors в папке diffusion_models
    files = scan_files(CHECKPOINT_DIR, (".safetensors", ".ckpt"))
    return JSONResponse(content={"checkpoints": files})

@app.get("/api/loras")
async def get_loras():
    # Ищем лоры
    files = scan_files(LORA_DIR, (".safetensors", ".pt"))
    return JSONResponse(content={"loras": files})

@app.get("/api/images")
async def get_images():
    # Ищем картинки, загруженные пользователем (jpg, png, webp)
    # ComfyUI хранит их в папке input
    files = scan_files(INPUT_DIR, (".jpg", ".jpeg", ".png", ".webp"))
    return JSONResponse(content={"images": files})

if __name__ == "__main__":
    print(f"🚀 Server running on 0.0.0.0:8099")
    print(f"📂 Scanning Models: {CHECKPOINT_DIR}")
    print(f"📂 Scanning Input Images: {INPUT_DIR}")
    uvicorn.run(app, host="0.0.0.0", port=8099)