from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import os
import sys

app = FastAPI()

# Определяем пути
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Создаем папки, если их нет (чтобы сервер не падал при старте)
if not os.path.exists(TEMPLATE_DIR):
    os.makedirs(TEMPLATE_DIR)
    # Создаем заглушку, если индексного файла нет
    with open(os.path.join(TEMPLATE_DIR, "index.html"), "w") as f:
        f.write("<h1>WebApp Server is Running. Please upload index.html to templates folder.</h1>")

if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

# Подключаем статику и шаблоны
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATE_DIR)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

if __name__ == "__main__":
    # ВАЖНО: host="0.0.0.0" позволяет доступ снаружи (через RunPod Proxy)
    # Порт 8099 - тот, который мы открыли в настройках пода
    print("🚀 Starting WebApp Server on 0.0.0.0:8099...")
    uvicorn.run(app, host="0.0.0.0", port=8099)
