#!/bin/bash
# NeuroGraph Installer v7.0

WORKSPACE="/workspace"
LORA_PATH="/workspace/ComfyUI/models/loras/Qwen_Pack"
WC_PATH="/workspace/ComfyUI/wildcards"

echo "🎨 Начинаю установку..."

# Подготовка папок
mkdir -p "$LORA_PATH"
mkdir -p "$WC_PATH"
mkdir -p "$WORKSPACE/logs"

# Копирование файлов
cp /workspace/installer/bot.py "$WORKSPACE/bot.py"
cp /workspace/installer/*.json "$WORKSPACE/" 2>/dev/null
cp -r /workspace/installer/wildcards/* "$WC_PATH/" 2>/dev/null

# Скачивание LoRAs (без остановки при ошибках)
echo "⬇️ Загрузка моделей..."
HEADER_CMD=""
[ ! -z "$HF_TOKEN" ] && HEADER_CMD="--header='Authorization: Bearer $HF_TOKEN'"

wget -nv $HEADER_CMD -nc -O "$LORA_PATH/Qwen4Play_v2.safetensors" "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/Qwen4Play_v2.safetensors?download=true" || true
wget -nv $HEADER_CMD -nc -O "$LORA_PATH/Qwen_Snofs_1_3.safetensors" "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/Qwen_Snofs_1_3.safetensors?download=true" || true
wget -nv $HEADER_CMD -nc -O "$LORA_PATH/breast_slider_qwen_v1.safetensors" "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/breast_slider_qwen_v1.safetensors?download=true" || true
wget -nv $HEADER_CMD -nc -O "$LORA_PATH/hips_size_slider_v1.safetensors" "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/hips_size_slider_v1.safetensors?download=true" || true

# Установка библиотек и запуск бота
pip install python-telegram-bot requests websocket-client > /dev/null 2>&1
nohup python "$WORKSPACE/bot.py" > "$WORKSPACE/logs/bot.log" 2>&1 &

echo "✅ Установка NeuroGraph завершена."
