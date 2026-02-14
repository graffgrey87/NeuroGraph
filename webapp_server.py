import uvicorn
import os
import json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# ПУТИ (Адаптировано под RunPod и ваш скрипт)
BASE_DIR = "/workspace/ComfyUI"
DIRS = {
    "loras": os.path.join(BASE_DIR, "models/loras"),
    "checkpoints": os.path.join(BASE_DIR, "models/diffusion_models")
}

# Шаблоны (HTML)
templates = Jinja2Templates(directory="/workspace/templates")

def get_files(folder):
    """Сканирует папку и возвращает чистый список файлов для выпадающего меню"""
    if not os.path.exists(folder): return []
    files = []
    for root, _, filenames in os.walk(folder):
        for f in filenames:
            if f.endswith(".safetensors") or f.endswith(".ckpt") or f.endswith(".gguf"):
                files.append(f)
    return sorted(files)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "loras": get_files(DIRS["loras"]),
        "checkpoints": get_files(DIRS["checkpoints"])
    })

if __name__ == "__main__":
    # Запускаем на 0.0.0.0, порт 8084 (как прописано в install.sh)
    print("🚀 WebApp Server starting on port 8084...")
    uvicorn.run(app, host="0.0.0.0", port=8084)
