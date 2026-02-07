#!/bin/bash
# NeuroGraph Installer v6.0 (System Recovery Mode)

WORKSPACE="/workspace"
LORA_PATH="/workspace/ComfyUI/models/loras/Qwen_Pack"
WC_PATH="/workspace/ComfyUI/wildcards"

echo "🎨 [NeuroGraph] Начинаю установку компонентов..."

# 1. Файлы бота и конфиги
cp /workspace/installer/bot.py "$WORKSPACE/bot.py"
cp /workspace/installer/*.json "$WORKSPACE/" 2>/dev/null

# 2. Wildcards (создаем папку если нет и копируем)
mkdir -p "$WC_PATH"
cp -r /workspace/installer/wildcards/* "$WC_PATH/" 2>/dev/null

# 3. LoRAs (Тихое скачивание)
mkdir -p "$LORA_PATH"
HEADER_CMD=""
if [ ! -z "$HF_TOKEN" ]; then
    HEADER_CMD="--header='Authorization: Bearer $HF_TOKEN'"
fi

wget -nv $HEADER_CMD -nc -O "$LORA_PATH/Qwen4Play_v2.safetensors" "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/Qwen4Play_v2.safetensors?download=true"
wget -nv $HEADER_CMD -nc -O "$LORA_PATH/Qwen_Snofs_1_3.safetensors" "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/Qwen_Snofs_1_3.safetensors?download=true"
wget -nv $HEADER_CMD -nc -O "$LORA_PATH/breast_slider_qwen_v1.safetensors" "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/breast_slider_qwen_v1.safetensors?download=true"
wget -nv $HEADER_CMD -nc -O "$LORA_PATH/hips_size_slider_v1.safetensors" "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/hips_size_slider_v1.safetensors?download=true"

# 4. Запуск бота
echo "🤖 [NeuroGraph] Запуск Telegram бота..."
pip install python-telegram-bot requests websocket-client > /dev/null 2>&1
cd "$WORKSPACE"
nohup python bot.py > /workspace/logs/bot.log 2>&1 &

echo "✅ [NeuroGraph] Установка завершена успешно!"
