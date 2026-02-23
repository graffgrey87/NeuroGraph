"""
fast_downloader.py — Асинхронный движок загрузки моделей для NeuroGraph.

Скачивает файлы из HuggingFace (прямые ссылки) в /workspace/ComfyUI/models/
с отслеживанием прогресса и поддержкой отмены.
"""
import os
import json
import asyncio
import time

BASE_DIR = os.environ.get("WORKSPACE_DIR", "/workspace")
MODELS_DIR = os.path.join(BASE_DIR, "ComfyUI/models")
PRESETS_FILE = os.path.join(BASE_DIR, "presets.json")

# ==========================================
# 📦 PRESETS I/O
# ==========================================

def load_presets() -> dict:
    """Загружает presets.json. Возвращает {'categories': {}, 'presets': {}}."""
    if not os.path.exists(PRESETS_FILE):
        return {"categories": {}, "presets": {}}
    try:
        with open(PRESETS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Ошибка чтения presets.json: {e}")
        return {"categories": {}, "presets": {}}


def save_presets(data: dict):
    """Сохраняет presets.json."""
    try:
        with open(PRESETS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Ошибка записи presets.json: {e}")


def add_preset(key: str, name: str, category: str, files: list[dict]) -> bool:
    """
    Добавляет пользовательский пресет.
    files: [{"url": "...", "folder": "loras", "filename": null}, ...]
    """
    data = load_presets()
    data["presets"][key] = {
        "name": name,
        "category": category,
        "size": "?",
        "files": files
    }
    if category not in data.get("categories", {}):
        data.setdefault("categories", {})[category] = {"icon": "📦"}
    save_presets(data)
    return True


def get_categories_with_counts() -> list[tuple[str, str, int]]:
    """Возвращает [(category, icon, count), ...] отсортированный по имени."""
    data = load_presets()
    cats = data.get("categories", {})
    presets = data.get("presets", {})
    
    counts = {}
    for p in presets.values():
        cat = p.get("category", "Custom")
        counts[cat] = counts.get(cat, 0) + 1
    
    result = []
    for cat, info in cats.items():
        if counts.get(cat, 0) > 0:
            result.append((cat, info.get("icon", "📦"), counts[cat]))
    return sorted(result, key=lambda x: x[0])


def get_presets_by_category(category: str) -> list[tuple[str, dict]]:
    """Возвращает [(key, preset_info), ...] для категории."""
    data = load_presets()
    result = []
    for key, info in data.get("presets", {}).items():
        if info.get("category") == category:
            result.append((key, info))
    return sorted(result, key=lambda x: x[1].get("name", ""))


def get_preset_info(key: str) -> dict | None:
    """Возвращает информацию о пресете по ключу."""
    data = load_presets()
    return data.get("presets", {}).get(key)


# ==========================================
# 🧩 COMPONENT CATALOG
# ==========================================

def get_components(comp_type: str) -> list[tuple[str, dict]]:
    """
    Возвращает [(key, info), ...] для типа: 'models', 'vae', 'text_encoders'.
    Отсортировано по имени.
    """
    data = load_presets()
    comps = data.get("components", {}).get(comp_type, {})
    return sorted(comps.items(), key=lambda x: x[1].get("name", ""))


def get_component(comp_type: str, key: str) -> dict | None:
    """Возвращает информацию о компоненте."""
    data = load_presets()
    return data.get("components", {}).get(comp_type, {}).get(key)


def build_preset(name: str, model_key: str, vae_key: str, encoder_key: str) -> str | None:
    """
    Собирает пресет из выбранных компонентов.
    Возвращает ключ нового пресета или None при ошибке.
    """
    data = load_presets()
    comps = data.get("components", {})
    
    model = comps.get("models", {}).get(model_key)
    vae = comps.get("vae", {}).get(vae_key)
    encoder = comps.get("text_encoders", {}).get(encoder_key)
    
    if not model or not vae or not encoder:
        return None
    
    key = f"CUSTOM_{name.upper().replace(' ', '_')}"
    files = []
    for comp in [model, vae, encoder]:
        files.append({
            "url": comp["url"],
            "folder": comp["folder"],
            "filename": comp.get("filename")
        })
    
    data["presets"][key] = {
        "name": name,
        "category": "Custom",
        "size": "?",
        "files": files
    }
    if "Custom" not in data.get("categories", {}):
        data.setdefault("categories", {})["Custom"] = {"icon": "📦"}
    save_presets(data)
    return key


def add_component(comp_type: str, key: str, name: str, url: str, folder: str) -> bool:
    """Добавляет компонент в каталог."""
    if comp_type not in ("models", "vae", "text_encoders"):
        return False
    data = load_presets()
    data.setdefault("components", {}).setdefault(comp_type, {})[key] = {
        "name": name,
        "url": url,
        "folder": folder,
        "filename": url.split("/")[-1].split("?")[0]
    }
    save_presets(data)
    return True


# ==========================================
# ⬇️ DOWNLOAD ENGINE
# ==========================================

# Флаги отмены (per-user)
download_cancel_flags: dict[int, bool] = {}


def _get_filename_from_url(url: str, custom_filename: str | None = None) -> str:
    """Определяет имя файла из URL или custom_filename."""
    if custom_filename:
        return custom_filename
    filename = os.path.basename(url.split("?")[0])
    return filename if filename and "." in filename else "downloaded_file"


async def download_file(
    url: str,
    dest_folder: str,
    custom_filename: str | None = None,
    on_progress=None,
    uid: int = 0,
) -> tuple[str, str]:
    """
    Скачивает один файл по URL.
    
    on_progress: async callback(downloaded_bytes, total_bytes, filename)
    
    Возвращает: ("DOWNLOADED"|"SKIP", filename)
    Raises RuntimeError при ошибке.
    """
    filename = _get_filename_from_url(url, custom_filename)
    filepath = os.path.join(dest_folder, filename)
    os.makedirs(dest_folder, exist_ok=True)
    
    # Пропуск существующих
    if os.path.isfile(filepath) and os.path.getsize(filepath) > 0:
        return "SKIP", filename
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    # Токен HuggingFace (для gated repos)
    hf_token = os.environ.get("HF_TOKEN")
    if hf_token and "huggingface.co" in url:
        headers["Authorization"] = f"Bearer {hf_token}"
    
    try:
        # Пробуем aria2c (16 потоков) для максимальной скорости
        import subprocess
        import re
        
        cmd = [
            "aria2c",
            "--console-log-level=notice",
            "--summary-interval=1",
            "-d", dest_folder,
            "-o", filename,
            "-x", "16",
            "-s", "16",
            "-j", "16",
            "-k", "1M"
        ]
        if hf_token and "huggingface.co" in url:
            cmd.extend(["--header", f"Authorization: Bearer {hf_token}"])
        cmd.append(url)
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        
        last_report_time = 0
        while True:
            # Проверка отмены
            if uid and download_cancel_flags.get(uid):
                process.terminate()
                if os.path.exists(filepath):
                    os.remove(filepath)
                raise RuntimeError("⛔ Отменено")
                
            if process.stdout is None:
                break
                
            line = await process.stdout.readline()
            if not line:
                break
            
            line_str = line.decode('utf-8', errors='ignore')
            # Парсинг вывода aria2c вида:
            # [#12345 1.2GiB/4.5GiB(26%) CN:16 DL:102MiB]
            if on_progress and "%" in line_str and ("GiB" in line_str or "MiB" in line_str):
                now = time.time()
                if now - last_report_time >= 3.0:  # обновляем прогресс-бар раз в 3 сек
                    match = re.search(r'\((\d+)%\)', line_str)
                    if match:
                        percent = int(match.group(1))
                        # Если не знаем точный размер, эмулируем "скачано/всего" через проценты
                        await on_progress(percent, 100, filename)
                        last_report_time = now
        
        await process.wait()
        if process.returncode != 0:
            raise RuntimeError(f"aria2c error code: {process.returncode}")
            
        return "DOWNLOADED", filename

        
    except Exception as e:
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except:
                pass
        raise RuntimeError(f"Ошибка: {filename} — {e}")


async def download_preset(
    preset_key: str,
    on_progress=None,
    uid: int = 0,
) -> dict:
    """
    Скачивает все файлы пресета.
    
    on_progress: async callback(current_file, total_files, downloaded_bytes, total_bytes, filename)
    
    Возвращает: {"downloaded": [...], "skipped": [...], "failed": [...]}
    """
    info = get_preset_info(preset_key)
    if not info:
        raise ValueError(f"Пресет '{preset_key}' не найден")
    
    files = info.get("files", [])
    total = len(files)
    result = {"downloaded": [], "skipped": [], "failed": []}
    
    download_cancel_flags[uid] = False
    
    for idx, fdata in enumerate(files, 1):
        # Проверка отмены
        if uid and download_cancel_flags.get(uid):
            result["failed"].append("⛔ Отменено пользователем")
            break
        
        url = fdata["url"]
        folder = fdata["folder"]
        custom_fn = fdata.get("filename")
        dest = os.path.join(MODELS_DIR, folder)
        
        async def file_progress(dl_bytes, total_bytes, fname, _idx=idx):
            if on_progress:
                await on_progress(_idx, total, dl_bytes, total_bytes, fname)
        
        try:
            status, filename = await download_file(
                url, dest, custom_fn, on_progress=file_progress, uid=uid
            )
            if status == "DOWNLOADED":
                result["downloaded"].append(filename)
            else:
                result["skipped"].append(filename)
        except RuntimeError as e:
            result["failed"].append(str(e))
            if "Отменено" in str(e):
                break
    
    return result


async def download_url(
    url: str,
    folder: str = "diffusion_models",
    on_progress=None,
    uid: int = 0,
) -> tuple[str, str]:
    """
    Скачивает файл по произвольной ссылке.
    
    Возвращает: ("DOWNLOADED"|"SKIP", filename)
    """
    dest = os.path.join(MODELS_DIR, folder)
    return await download_file(url, dest, on_progress=on_progress, uid=uid)
