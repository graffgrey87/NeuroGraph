#!/bin/bash
# NeuroGraph Installer v10 (Watcher Mode)

WORKSPACE="/workspace"
LORA_PATH="/workspace/ComfyUI/models/loras/Qwen_Pack"
WC_PATH="/workspace/ComfyUI/wildcards"

echo "🎨 [NeuroGraph] ComfyUI уже работает. Начинаю фоновую загрузку..."

# 1. Подготовка папок
mkdir -p "$LORA_PATH"
mkdir -p "$WC_PATH"
mkdir -p "$WORKSPACE/logs"

# 2. Файлы бота
cp /workspace/installer/bot.py "$WORKSPACE/bot.py"
cp /workspace/installer/*.json "$WORKSPACE/" 2>/dev/null
cp -r /workspace/installer/wildcards/* "$WC_PATH/" 2>/dev/null

# 3. Функция скачивания
download_model() {
    local url=$1
    local dest=$2
    if [ -z "$HF_TOKEN" ]; then
        wget -q -nc -O "$dest" "$url"
    else
        wget -q --header "Authorization: Bearer $HF_TOKEN" -nc -O "$dest" "$url"
    fi
}

# 4. Скачивание (прямо в потоке, диск уже свободен)
echo "⬇️ Качаю Лоры..."
download_model "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/Qwen4Play_v2.safetensors?download=true" "$LORA_PATH/Qwen4Play_v2.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/Qwen_Snofs_1_3.safetensors?download=true" "$LORA_PATH/Qwen_Snofs_1_3.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/breast_slider_qwen_v1.safetensors?download=true" "$LORA_PATH/breast_slider_qwen_v1.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/hips_size_slider_v1.safetensors?download=true" "$LORA_PATH/hips_size_slider_v1.safetensors"

# 5. Запуск бота
echo "🤖 Запуск бота..."
pip install python-telegram-bot requests websocket-client > /dev/null 2>&1
cd "$WORKSPACE"
nohup python bot.py > /workspace/logs/bot.log 2>&1 &

echo "✅ [NeuroGraph] Всё готово! Бот запущен, Лоры на месте."
