#!/bin/bash

# ==========================================
# 🛠 NEUROGRAPH INSTALLER v5.5 (FINAL MERGE)
# ==========================================

# ПУТИ
VENV_PYTHON="/workspace/venv/bin/python"
VENV_PIP="/workspace/venv/bin/pip"
ROOT_MODELS="/workspace/ComfyUI/models"
L_PATH="$ROOT_MODELS/loras"
CKPT_PATH="$ROOT_MODELS/diffusion_models"
VAE_PATH="$ROOT_MODELS/vae"
CLIP_PATH="$ROOT_MODELS/text_encoders"
CN_PATH="/workspace/ComfyUI/custom_nodes"

# 1. ЖДЕМ ПОРТ 3000
echo "⏳ Жду порт 3000..."
while ! wget -q --spider http://127.0.0.1:3000; do
  sleep 2
done
echo "✅ Порт 3000 активен."

# 2. БИБЛИОТЕКИ
echo "📦 Ставлю библиотеки..."
$VENV_PIP install python-telegram-bot requests websocket-client aiohttp fastapi uvicorn Jinja2 python-multipart > /dev/null 2>&1

# 3. УСТАНОВКА НОД
echo "🧩 Ставлю ноды (Только отсутствующие)..."
mkdir -p $CN_PATH
cd $CN_PATH

# --- [GROUP 1] Старые ноды (из вашего скрипта) ---
[ ! -d "mikey_nodes" ] && git clone https://github.com/bash-j/mikey_nodes.git
[ ! -d "comfy-image-saver" ] && git clone https://github.com/giriss/comfy-image-saver.git
[ ! -d "ComfyUI-Custom-Scripts" ] && git clone https://github.com/pythongosssss/ComfyUI-Custom-Scripts.git

# --- [GROUP 2] Новые ноды (Для Flux) ---
# Inpaint (Flux)
[ ! -d "comfyui-inpaint-cropandstitch" ] && git clone https://github.com/ltdrdata/comfyui-inpaint-cropandstitch.git
# Basic Data Handling (StableLlama - Flux requirement)
[ ! -d "ComfyUI-basic_data_handling" ] && git clone https://github.com/StableLlama/ComfyUI-basic_data_handling.git


# 4. ЗАГРУЗКА МОДЕЛЕЙ
echo "⬇️ Менеджер загрузок..."
mkdir -p "$L_PATH" "$CKPT_PATH" "$VAE_PATH" "$CLIP_PATH"

# Функция загрузки (Ваша, без изменений логики)
download_model() {
    url="$1"
    file="$2"
    path="$3" # Аргумент пути
    
    # По дефолту в лоры
    if [ -z "$path" ]; then path="$L_PATH"; fi

    echo "---------------------------------------------------"
    echo "📥 Скачиваю: $file"
    
    if [ -f "$path/$file" ]; then
        echo "✅ Файл уже существует, пропускаю."
        return
    fi

    if [ -z "$HF_TOKEN" ]; then
        echo "⚠️ HF_TOKEN нет. Качаю публично..."
        wget -nc -O "$path/$file" "$url"
    else
        echo "🔒 HF_TOKEN найден."
        wget --header "Authorization: Bearer $HF_TOKEN" -nc -O "$path/$file" "$url"
    fi
}

# ==========================================
# 🅰️ QWEN (ТОЛЬКО ЛОРЫ)
# ==========================================
echo "🔹 [1/3] Загрузка Qwen LoRAs..."
download_model "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/Qwen4Play_v2.safetensors?download=true" "Qwen4Play_v2.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/Qwen_Snofs_1_3.safetensors?download=true" "Qwen_Snofs_1_3.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/breast_slider_qwen_v1.safetensors?download=true" "breast_slider_qwen_v1.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/hips_size_slider_v1.safetensors?download=true" "hips_size_slider_v1.safetensors"


# ==========================================
# 🅱️ FLUX SYSTEM (9B, FP8, VAE, ENC)
# ==========================================
echo "🔹 [2/3] Загрузка Flux Checkpoints & System..."

# Flux 9B (Original)
download_model "https://huggingface.co/black-forest-labs/FLUX.2-klein-9B/resolve/main/flux-2-klein-9b.safetensors?download=true" "flux-2-klein-9b.safetensors" "$CKPT_PATH"
# Flux 9B (FP8)
download_model "https://huggingface.co/black-forest-labs/FLUX.2-klein-9b-fp8/resolve/main/flux-2-klein-9b-fp8.safetensors?download=true" "flux-2-klein-9b-fp8.safetensors" "$CKPT_PATH"

# Encoders & VAE
download_model "https://huggingface.co/Comfy-Org/vae-text-encorder-for-flux-klein-9b/resolve/main/split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors?download=true" "qwen_3_8b_fp8mixed.safetensors" "$CLIP_PATH"
download_model "https://huggingface.co/Comfy-Org/vae-text-encorder-for-flux-klein-9b/resolve/main/split_files/text_encoders/qwen_3_8b.safetensors?download=true" "qwen_3_8b.safetensors" "$CLIP_PATH"
download_model "https://huggingface.co/Comfy-Org/vae-text-encorder-for-flux-klein-9b/resolve/main/split_files/vae/flux2-vae.safetensors?download=true" "flux2-vae.safetensors" "$VAE_PATH"


# ==========================================
# 🆎 FLUX LORAS (ПОЛНЫЙ СПИСОК)
# ==========================================
echo "🔹 [3/3] Загрузка Flux LoRAs..."
download_model "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/1A_Back_Pose_Enhancer.safetensors?download=true" "1A_Back_Pose_Enhancer.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/Breast_Implanter_v2.safetensors?download=true" "Breast_Implanter_v2.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/F2K_9b_Siren_X_lora_v1.safetensors?download=true" "F2K_9b_Siren_X_lora_v1.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/Realism_Engine_Klein_V1.safetensors?download=true" "Realism_Engine_Klein_V1.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/anus_fem_klein.safetensors?download=true" "anus_fem_klein.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/ass_slider_klein9b_v09_20260202_200942.safetensors?download=true" "ass_slider_klein9b_v09_20260202_200942.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/breast_slider_klein9b_v09_20260202_070616.safetensors?download=true" "breast_slider_klein9b_v09_20260202_070616.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/cameltoe_klein.safetensors?download=true" "cameltoe_klein.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/f2_klein9b_macromastia_clothed.safetensors?download=true" "f2_klein9b_macromastia_clothed.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/f2_klein9b_macromastia_naked.safetensors?download=true" "f2_klein9b_macromastia_naked.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/f2k_selfies_13400s.safetensors?download=true" "f2k_selfies_13400s.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/fancy-lingerie-klein.safetensors?download=true" "fancy-lingerie-klein.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/flux2klein_vulva_and_anus_from_behind_v1.safetensors?download=true" "flux2klein_vulva_and_anus_from_behind_v1.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/klein_ahegao.safetensors?download=true" "klein_ahegao.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/klein_snofs_v1.safetensors?download=true" "klein_snofs_v1.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/lying-back.safetensors?download=true" "lying-back.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/nipplediffusion-f2-klein-9b_v2.safetensors?download=true" "nipplediffusion-f2-klein-9b_v2.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/nude_woman_v1.safetensors?download=true" "nude_woman_v1.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/psxCheeks_v2_FLUX.K9b.safetensors?download=true" "psxCheeks_v2_FLUX.K9b.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/pussydiffusion-f2-klein-9b_v2.safetensors?download=true" "pussydiffusion-f2-klein-9b_v2.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/pussymix_datass.safetensors?download=true" "pussymix_datass.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/razzz_nude_woman_klein_v1.safetensors?download=true" "razzz_nude_woman_klein_v1.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/voluptuous_slider_klein9b_v05_20260203_155139.safetensors?download=true" "voluptuous_slider_klein9b_v05_20260203_155139.safetensors"

echo "---------------------------------------------------"
echo "📂 ПРОВЕРКА ЗАГРУЗОК:"
ls -lh "$L_PATH" | head -n 5
echo "..."
echo "---------------------------------------------------"

# 5. КОПИРОВАНИЕ ФАЙЛОВ
echo "🤖 Копирую файлы бота и конфиги..."
cp /workspace/installer/bot.py /workspace/bot.py
cp /workspace/installer/webapp_server.py /workspace/webapp_server.py
# Копируем JSON (который вы залили в гит)
cp /workspace/installer/*.json /workspace/ 2>/dev/null
# Шаблоны WebApp
mkdir -p /workspace/templates
cp /workspace/installer/templates/index.html /workspace/templates/ 2>/dev/null
# Wildcards
[ -d "/workspace/installer/wildcards" ] && cp -r "/workspace/installer/wildcards" "/workspace/ComfyUI/"

# 6. ПЕРЕЗАПУСК
echo "🔄 Убиваю процессы..."
pkill -f "python main.py"
pkill -f "bot.py"
pkill -f "webapp_server.py"
sleep 5

echo "🌐 Старт WebApp (8084)..."
nohup $VENV_PYTHON /workspace/webapp_server.py > /workspace/webapp.log 2>&1 &

echo "🤖 Старт Бота..."
nohup $VENV_PYTHON /workspace/bot.py > /workspace/bot.log 2>&1 &

echo "🚀 Старт ComfyUI (Foreground)..."
cd /workspace/ComfyUI
$VENV_PYTHON main.py --listen 0.0.0.0 --port 3000
