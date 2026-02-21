#!/bin/bash

# ==========================================
# 💎 NEUROGRAPH INSTALLER v6.0 (ARIA2 TURBO)
# ==========================================

VENV_PYTHON="/workspace/venv/bin/python"
VENV_PIP="/workspace/venv/bin/pip"
ROOT_MODELS="/workspace/ComfyUI/models"
L_PATH="$ROOT_MODELS/loras"
CKPT_PATH="$ROOT_MODELS/diffusion_models"
VAE_PATH="$ROOT_MODELS/vae"
CLIP_PATH="$ROOT_MODELS/text_encoders"
CN_PATH="/workspace/ComfyUI/custom_nodes"
MAX_PARALLEL=4

# 1. ЖДЕМ ПОРТ 3000
echo "⏳ Жду порт 3000..."
while ! wget -q --spider http://127.0.0.1:3000; do
  sleep 2
done
echo "✅ Порт 3000 активен."

# 2. ARIA2 + БИБЛИОТЕКИ
echo "📦 Устанавливаю aria2 и библиотеки..."
apt-get update -qq && apt-get install -y -qq aria2 > /dev/null 2>&1
$VENV_PIP install python-telegram-bot requests websocket-client aiohttp fastapi uvicorn Jinja2 python-multipart > /dev/null 2>&1

USE_ARIA2=false
if command -v aria2c &> /dev/null; then
    USE_ARIA2=true
    echo "🚀 aria2c найден — турбо-режим активен (x16 потоков)"
else
    echo "⚠️ aria2c не найден — fallback на wget"
fi

# 3. НОДЫ
echo "🧩 Ставлю ноды..."
mkdir -p $CN_PATH
cd $CN_PATH

[ ! -d "mikey_nodes" ] && git clone --depth 1 https://github.com/bash-j/mikey_nodes.git &
[ ! -d "comfy-image-saver" ] && git clone --depth 1 https://github.com/giriss/comfy-image-saver.git &
[ ! -d "ComfyUI-Custom-Scripts" ] && git clone --depth 1 https://github.com/pythongosssss/ComfyUI-Custom-Scripts.git &
[ ! -d "comfyui-inpaint-cropandstitch" ] && git clone --depth 1 https://github.com/ltdrdata/comfyui-inpaint-cropandstitch.git &
[ ! -d "ComfyUI-basic_data_handling" ] && git clone --depth 1 https://github.com/StableLlama/ComfyUI-basic_data_handling.git &
wait
echo "✅ Ноды готовы."

# 4. ЗАГРУЗЧИК
echo "⬇️ Менеджер загрузок..."
mkdir -p "$L_PATH" "$CKPT_PATH" "$VAE_PATH" "$CLIP_PATH"

download_model() {
    local url="$1"
    local file="$2"
    local path="${3:-$L_PATH}"

    if [ -f "$path/$file" ] && [ -s "$path/$file" ]; then
        echo "  ✅ $file (exists)"
        return 0
    fi

    rm -f "$path/$file" 2>/dev/null

    echo "  📥 $file ..."
    if $USE_ARIA2; then
        local -a cmd=(aria2c -x 16 -s 16 -k 1M --file-allocation=none --auto-file-renaming=false --allow-overwrite=true -d "$path" -o "$file")
        [ -n "$HF_TOKEN" ] && cmd+=(--header="Authorization: Bearer $HF_TOKEN")
        cmd+=("$url")
        "${cmd[@]}"
        local rc=$?
        if [ $rc -ne 0 ] || [ ! -s "$path/$file" ]; then
            echo "  ⚠️ aria2c failed (rc=$rc), trying wget..."
            rm -f "$path/$file" 2>/dev/null
            if [ -n "$HF_TOKEN" ]; then
                wget -q --show-progress --header "Authorization: Bearer $HF_TOKEN" -O "$path/$file" "$url"
            else
                wget -q --show-progress -O "$path/$file" "$url"
            fi
        fi
    else
        if [ -n "$HF_TOKEN" ]; then
            wget -q --show-progress --header "Authorization: Bearer $HF_TOKEN" -O "$path/$file" "$url"
        else
            wget -q --show-progress -O "$path/$file" "$url"
        fi
    fi

    if [ -s "$path/$file" ]; then
        echo "  ✅ $file OK"
    else
        echo "  ❌ $file FAILED"
        rm -f "$path/$file" 2>/dev/null
    fi
}

download_bg() {
    download_model "$@" &
}

wait_batch() {
    wait
}

# ==========================================
# 🅰️ БОЛЬШИЕ ФАЙЛЫ (последовательно, 16 потоков каждый)
# ==========================================
echo ""
echo "━━━ CHECKPOINTS ━━━"
download_model "https://huggingface.co/black-forest-labs/FLUX.2-klein-9B/resolve/main/flux-2-klein-9b.safetensors?download=true" "flux-2-klein-9b.safetensors" "$CKPT_PATH"
download_model "https://huggingface.co/black-forest-labs/FLUX.2-klein-9b-fp8/resolve/main/flux-2-klein-9b-fp8.safetensors?download=true" "flux-2-klein-9b-fp8.safetensors" "$CKPT_PATH"

echo ""
echo "━━━ CLIP & VAE ━━━"
download_model "https://huggingface.co/Comfy-Org/vae-text-encorder-for-flux-klein-9b/resolve/main/split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors?download=true" "qwen_3_8b_fp8mixed.safetensors" "$CLIP_PATH"
download_model "https://huggingface.co/Comfy-Org/vae-text-encorder-for-flux-klein-9b/resolve/main/split_files/text_encoders/qwen_3_8b.safetensors?download=true" "qwen_3_8b.safetensors" "$CLIP_PATH"
download_model "https://huggingface.co/Comfy-Org/vae-text-encorder-for-flux-klein-9b/resolve/main/split_files/vae/flux2-vae.safetensors?download=true" "flux2-vae.safetensors" "$VAE_PATH"

# ==========================================
# 🅱️ ЛОРЫ — ПАЧКАМИ ПО 4 ПАРАЛЛЕЛЬНО
# ==========================================
echo ""
echo "━━━ QWEN LORAS (batch ${MAX_PARALLEL}x) ━━━"
download_bg "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/Qwen4Play_v2.safetensors?download=true" "Qwen4Play_v2.safetensors"
download_bg "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/Qwen_Snofs_1_3.safetensors?download=true" "Qwen_Snofs_1_3.safetensors"
download_bg "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/breast_slider_qwen_v1.safetensors?download=true" "breast_slider_qwen_v1.safetensors"
download_bg "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/hips_size_slider_v1.safetensors?download=true" "hips_size_slider_v1.safetensors"
wait_batch

echo ""
echo "━━━ FLUX LORAS — batch 1/6 ━━━"
download_bg "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/1A_Back_Pose_Enhancer.safetensors?download=true" "1A_Back_Pose_Enhancer.safetensors"
download_bg "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/Breast_Implanter_v2.safetensors?download=true" "Breast_Implanter_v2.safetensors"
download_bg "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/F2K_9b_Siren_X_lora_v1.safetensors?download=true" "F2K_9b_Siren_X_lora_v1.safetensors"
download_bg "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/Realism_Engine_Klein_V1.safetensors?download=true" "Realism_Engine_Klein_V1.safetensors"
wait_batch

echo "━━━ FLUX LORAS — batch 2/6 ━━━"
download_bg "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/anus_fem_klein.safetensors?download=true" "anus_fem_klein.safetensors"
download_bg "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/ass_slider_klein9b_v09_20260202_200942.safetensors?download=true" "ass_slider_klein9b_v09_20260202_200942.safetensors"
download_bg "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/breast_slider_klein9b_v09_20260202_070616.safetensors?download=true" "breast_slider_klein9b_v09_20260202_070616.safetensors"
download_bg "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/cameltoe_klein.safetensors?download=true" "cameltoe_klein.safetensors"
wait_batch

echo "━━━ FLUX LORAS — batch 3/6 ━━━"
download_bg "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/f2_klein9b_macromastia_clothed.safetensors?download=true" "f2_klein9b_macromastia_clothed.safetensors"
download_bg "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/f2_klein9b_macromastia_naked.safetensors?download=true" "f2_klein9b_macromastia_naked.safetensors"
download_bg "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/f2k_selfies_13400s.safetensors?download=true" "f2k_selfies_13400s.safetensors"
download_bg "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/fancy-lingerie-klein.safetensors?download=true" "fancy-lingerie-klein.safetensors"
wait_batch

echo "━━━ FLUX LORAS — batch 4/6 ━━━"
download_bg "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/flux2klein_vulva_and_anus_from_behind_v1.safetensors?download=true" "flux2klein_vulva_and_anus_from_behind_v1.safetensors"
download_bg "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/klein_ahegao.safetensors?download=true" "klein_ahegao.safetensors"
download_bg "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/klein_snofs_v1.safetensors?download=true" "klein_snofs_v1.safetensors"
download_bg "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/lying-back.safetensors?download=true" "lying-back.safetensors"
wait_batch

echo "━━━ FLUX LORAS — batch 5/6 ━━━"
download_bg "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/nipplediffusion-f2-klein-9b_v2.safetensors?download=true" "nipplediffusion-f2-klein-9b_v2.safetensors"
download_bg "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/nude_woman_v1.safetensors?download=true" "nude_woman_v1.safetensors"
download_bg "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/psxCheeks_v2_FLUX.K9b.safetensors?download=true" "psxCheeks_v2_FLUX.K9b.safetensors"
download_bg "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/pussydiffusion-f2-klein-9b_v2.safetensors?download=true" "pussydiffusion-f2-klein-9b_v2.safetensors"
wait_batch

echo "━━━ FLUX LORAS — batch 6/6 ━━━"
download_bg "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/pussymix_datass.safetensors?download=true" "pussymix_datass.safetensors"
download_bg "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/razzz_nude_woman_klein_v1.safetensors?download=true" "razzz_nude_woman_klein_v1.safetensors"
download_bg "https://huggingface.co/datasets/AleksandrGrey87/FLUX.2-klein-9B_LORAs/resolve/main/voluptuous_slider_klein9b_v05_20260203_155139.safetensors?download=true" "voluptuous_slider_klein9b_v05_20260203_155139.safetensors"
wait_batch

echo ""
echo "✅ Все модели загружены."

# 5. КОПИРОВАНИЕ И ЗАПУСК
echo "🤖 Копирую файлы бота..."
cp /workspace/installer/bot.py /workspace/bot.py
cp /workspace/installer/webapp_server.py /workspace/webapp_server.py
cp /workspace/installer/*.json /workspace/ 2>/dev/null
mkdir -p /workspace/templates
cp /workspace/installer/templates/index.html /workspace/templates/ 2>/dev/null
[ -d "/workspace/installer/wildcards" ] && cp -r "/workspace/installer/wildcards" "/workspace/ComfyUI/"

echo "🔄 Перезапуск служб..."
pkill -f "python main.py"
pkill -f "bot.py"
pkill -f "webapp_server.py"
sleep 5

echo "🌐 WebApp..."
nohup $VENV_PYTHON /workspace/webapp_server.py > /workspace/webapp.log 2>&1 &

echo "🤖 Бот..."
nohup $VENV_PYTHON /workspace/bot.py > /workspace/bot.log 2>&1 &

echo "🚀 Старт ComfyUI..."
cd /workspace/ComfyUI
$VENV_PYTHON main.py --listen 0.0.0.0 --port 3000
