#!/bin/bash
# NeuroGraph Installer v7.1 (Final Fix)

WORKSPACE="/workspace"
LORA_PATH="/workspace/ComfyUI/models/loras/Qwen_Pack"
WC_PATH="/workspace/ComfyUI/wildcards"

echo "🎨 Начинаю установку..."

# Подготовка
mkdir -p "$LORA_PATH"
mkdir -p "$WC_PATH"
mkdir -p "$WORKSPACE/logs"

# Файлы
cp /workspace/installer/bot.py "$WORKSPACE/bot.py"
cp /workspace/installer/*.json "$WORKSPACE/" 2>/dev/null
cp -r /workspace/installer/wildcards/* "$WC_PATH/" 2>/dev/null

# Функция скачивания (Безопасная)
download_model() {
    local url=$1
    local dest=$2
    echo "⬇️ Качаю: $(basename $dest)..."
    if [ -z "$HF_TOKEN" ]; then
        wget -q -nc -O "$dest" "$url"
    else
        # Используем --header прямо в команде, чтобы избежать проблем с кавычками bash
        wget -q --header "Authorization: Bearer $HF_TOKEN" -nc -O "$dest" "$url"
    fi
}

# Скачивание
download_model "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/Qwen4Play_v2.safetensors?download=true" "$LORA_PATH/Qwen4Play_v2.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/Qwen_Snofs_1_3.safetensors?download=true" "$LORA_PATH/Qwen_Snofs_1_3.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/breast_slider_qwen_v1.safetensors?download=true" "$LORA_PATH/breast_slider_qwen_v1.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/hips_size_slider_v1.safetensors?download=true" "$LORA_PATH/hips_size_slider_v1.safetensors"

# Бот
echo "🤖 Запуск бота..."
pip install python-telegram-bot requests websocket-client > /dev/null 2>&1
nohup python "$WORKSPACE/bot.py" > "$WORKSPACE/logs/bot.log" 2>&1 &

echo "✅ Установка завершена."
