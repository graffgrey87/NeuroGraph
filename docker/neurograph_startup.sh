#!/bin/bash
set -e

# ==========================================
# 🤖 NeuroGraph Startup Script (Post-Start)
# Запускается в фоне после старта контейнера
# ==========================================

WORKSPACE=${WORKSPACE:-/workspace}
VENV_PYTHON="${WORKSPACE}/venv/bin/python"
[ ! -f "$VENV_PYTHON" ] && VENV_PYTHON="/opt/venv/bin/python"

BASE_URL="https://raw.githubusercontent.com/graffgrey87/NeuroGraph/main"
MODELS_DIR="${WORKSPACE}/ComfyUI/models"
L_PATH="${MODELS_DIR}/loras"
CKPT_PATH="${MODELS_DIR}/diffusion_models"
VAE_PATH="${MODELS_DIR}/vae"
CLIP_PATH="${MODELS_DIR}/text_encoders"
MAX_PARALLEL=4

echo "=========================================="
echo "🤖 [NeuroGraph] Запуск фонового инициализатора..."
echo "=========================================="

# 1. ЖДЕМ ГОТОВНОСТИ COMFYUI (ПОРТ 3000)
echo "⏳ [NeuroGraph] Ожидание готовности ComfyUI на порту 3000..."
while ! curl -s http://127.0.0.1:3000 > /dev/null 2>&1; do
    sleep 2
done
echo "✅ [NeuroGraph] ComfyUI активен на порту 3000."

# 2. СКАЧИВАНИЕ / ОБНОВЛЕНИЕ ФАЙЛОВ НЕЙРОГРАФА С GITHUB
echo "📥 [NeuroGraph] Обновление файлов NeuroGraph..."
mkdir -p "${WORKSPACE}/templates"

download_if_needed() {
    local target="$1"
    local url="$2"
    wget -q -O "$target" "$url" || echo "⚠️ Не удалось обновить $target, используется локальная версия"
}

download_if_needed "${WORKSPACE}/bot.py" "${BASE_URL}/bot.py"
download_if_needed "${WORKSPACE}/fast_downloader.py" "${BASE_URL}/fast_downloader.py"
download_if_needed "${WORKSPACE}/webapp_server.py" "${BASE_URL}/webapp_server.py"
download_if_needed "${WORKSPACE}/TI2I_Flux2_Klein.json" "${BASE_URL}/TI2I_Flux2_Klein.json"
download_if_needed "${WORKSPACE}/presets.json" "${BASE_URL}/presets.json"

if [ ! -f "${WORKSPACE}/custom_presets.json" ]; then
    download_if_needed "${WORKSPACE}/custom_presets.json" "${BASE_URL}/custom_presets.json"
fi

download_if_needed "${WORKSPACE}/templates/index.html" "${BASE_URL}/templates/index.html"
download_if_needed "${WORKSPACE}/templates/status.html" "${BASE_URL}/templates/status.html"

# Если есть встроенные wildcards в образе, копируем их при отсутствии
if [ -d "/opt/neurograph/wildcards" ] && [ ! -d "${WORKSPACE}/wildcards" ]; then
    echo "📋 [NeuroGraph] Копирование wildcards из образа..."
    cp -r /opt/neurograph/wildcards "${WORKSPACE}/"
fi
if [ -d "${WORKSPACE}/wildcards" ]; then
    mkdir -p "${WORKSPACE}/ComfyUI"
    cp -r "${WORKSPACE}/wildcards" "${WORKSPACE}/ComfyUI/" 2>/dev/null || true
fi

# 3. ФУНКЦИЯ ЗАГРУЗКИ МОДЕЛЕЙ (ARIA2 / WGET)
USE_ARIA2=false
if command -v aria2c &> /dev/null; then
    USE_ARIA2=true
    echo "🚀 [NeuroGraph] aria2c активен для загрузки LoRA (x16 потоков)"
fi

download_model() {
    local url="$1"
    local file="$2"
    local path="${3:-$L_PATH}"

    mkdir -p "$path"
    if [ -f "$path/$file" ] && [ -s "$path/$file" ]; then
        return 0
    fi

    rm -f "$path/$file" 2>/dev/null
    if $USE_ARIA2; then
        local -a cmd=(aria2c -x 16 -s 16 -k 1M --file-allocation=none --auto-file-renaming=false --allow-overwrite=true --console-log-level=error --summary-interval=0 --download-result=hide -d "$path" -o "$file")
        [ -n "$HF_TOKEN" ] && cmd+=(--header="Authorization: Bearer $HF_TOKEN")
        cmd+=("$url")
        "${cmd[@]}" > /dev/null 2>&1 || true
    fi

    if [ ! -s "$path/$file" ]; then
        if [ -n "$HF_TOKEN" ]; then
            wget -q --header "Authorization: Bearer $HF_TOKEN" -O "$path/$file" "$url" || true
        else
            wget -q -O "$path/$file" "$url" || true
        fi
    fi

    if [ -s "$path/$file" ]; then
        echo "  ✅ Скачано: $file"
    else
        echo "  ⚠️ Не удалось загрузить: $file"
        rm -f "$path/$file" 2>/dev/null
    fi
}

download_bg() {
    download_model "$@" &
}

wait_batch() {
    wait
}

# 4. ФОНОВАЯ ПРОВЕРКА / ЗАГРУЗКА БАЗОВЫХ LORA (НЕ БЛОКИРУЕТ БОТА)
download_essential_loras() {
    echo "━━━ [NeuroGraph] Проверка наличия базовых LoRA ━━━"
    
    # Qwen LoRAs
    download_bg "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/Qwen4Play_v2.safetensors?download=true" "Qwen4Play_v2.safetensors"
    download_bg "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/Qwen_Snofs_1_3.safetensors?download=true" "Qwen_Snofs_1_3.safetensors"
    download_bg "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/breast_slider_qwen_v1.safetensors?download=true" "breast_slider_qwen_v1.safetensors"
    download_bg "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/hips_size_slider_v1.safetensors?download=true" "hips_size_slider_v1.safetensors"
    wait_batch

    # Flux LoRAs (batch 1)
    download_bg "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/1A_Back_Pose_Enhancer.safetensors?download=true" "1A_Back_Pose_Enhancer.safetensors"
    download_bg "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/Breast_Implanter_v2.safetensors?download=true" "Breast_Implanter_v2.safetensors"
    download_bg "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/F2K_9b_Siren_X_lora_v1.safetensors?download=true" "F2K_9b_Siren_X_lora_v1.safetensors"
    download_bg "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/Realism_Engine_Klein_V1.safetensors?download=true" "Realism_Engine_Klein_V1.safetensors"
    wait_batch

    echo "✅ [NeuroGraph] Проверка базовых LoRA завершена."
}

# 5. ПЕРЕЗАПУСК И СТАРТ СЛУЖБ
echo "🔄 [NeuroGraph] Запуск WebApp сервера и Telegram Бота..."
pkill -f "webapp_server.py" 2>/dev/null || true
pkill -f "bot.py" 2>/dev/null || true
sleep 2

# Запуск WebApp Server (8099)
echo "🌐 [NeuroGraph] Запуск WebApp на порту 8099..."
nohup "$VENV_PYTHON" "${WORKSPACE}/webapp_server.py" > "${WORKSPACE}/webapp.log" 2>&1 &

# Запуск Telegram Bot
if [ -n "$TG_TOKEN" ]; then
    echo "🤖 [NeuroGraph] Запуск Telegram бота..."
    PYTHONUNBUFFERED=1 nohup "$VENV_PYTHON" "${WORKSPACE}/bot.py" > "${WORKSPACE}/bot.log" 2>&1 &
    echo "✅ [NeuroGraph] Telegram бот запущен."
else
    echo "⚠️ [NeuroGraph] Переменная TG_TOKEN не задана. Бот не запущен."
fi

# Скачивание LoRA запускаем в фоне, чтобы бот уже отвечал пользователю
download_essential_loras &

echo "✨ [NeuroGraph] Инициализация служб завершена."
