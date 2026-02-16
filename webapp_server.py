from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

app = FastAPI()

# Разрешаем CORS (чтобы WebApp в Телеграме не ругался на домены)
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

# ✅ ПРАВИЛЬНЫЕ ПУТИ К МОДЕЛЯМ (FLUX)
LORA_DIR = "/workspace/ComfyUI/models/loras"
CHECKPOINT_DIR = "/workspace/ComfyUI/models/diffusion_models"  # Исправлено!

# Создаем системные папки (на всякий случай)
for d in [TEMPLATE_DIR, STATIC_DIR]:
    if not os.path.exists(d): os.makedirs(d)

# Заглушка, если index.html еще не залит
if not os.path.exists(os.path.join(TEMPLATE_DIR, "index.html")):
    with open(os.path.join(TEMPLATE_DIR, "index.html"), "w") as f:
        f.write("<h1>WebApp Server Active. Upload index.html!</h1>")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATE_DIR)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# --- API: СПИСОК ЛОР ---
@app.get("/api/loras")
async def get_loras():
    loras = []
    if os.path.exists(LORA_DIR):
        for root, dirs, files in os.walk(LORA_DIR):
            for file in files:
                if file.endswith(".safetensors"):
                    # Сохраняем относительный путь (например "Style/Anime.safetensors")
                    rel_path = os.path.relpath(os.path.join(root, file), LORA_DIR)
                    loras.append(rel_path)
    return JSONResponse(content={"loras": sorted(loras)})

# --- API: СПИСОК МОДЕЛЕЙ (FLUX) ---
@app.get("/api/checkpoints")
async def get_checkpoints():
    ckpts = []
    if os.path.exists(CHECKPOINT_DIR):
        for root, dirs, files in os.walk(CHECKPOINT_DIR):
            for file in files:
                if file.endswith((".safetensors", ".ckpt")):
                    ckpts.append(file)
    else:
        print(f"❌ ОШИБКА: Папка не найдена: {CHECKPOINT_DIR}")
        
    return JSONResponse(content={"checkpoints": sorted(ckpts)})

if __name__ == "__main__":
    # СЛУШАЕМ 0.0.0.0:8099
    print(f"🚀 Server running on port 8099. Scanning: {CHECKPOINT_DIR}")
    uvicorn.run(app, host="0.0.0.0", port=8099)
