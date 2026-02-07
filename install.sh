#!/bin/bash

# === НАСТРОЙКИ ===
WORKSPACE="/workspace"
COMFY_DIR="/workspace/ComfyUI"
LORA_PATH="$COMFY_DIR/models/loras/Qwen_Pack"
WC_PATH="$COMFY_DIR/wildcards"

echo "🚀 ЗАПУСК УСТАНОВКИ (Silent Mode)..."

# 1. Библиотеки (тихо)
pip install python-telegram-bot requests websocket-client > /dev/null 2>&1

# 2. Файлы
cp bot.py "$WORKSPACE/bot.py"
cp *.json "$WORKSPACE/" 2>/dev/null

# 3. Wildcards
mkdir -p "$WC_PATH"
cp -r wildcards/* "$WC_PATH/" 2>/dev/null

# 4. ЛОРЫ
mkdir -p "$LORA_PATH"
echo "⬇️ Скачивание LoRAs (без лишнего шума)..."

if [ -z "$HF_TOKEN" ]; then
    HEADER=""
else
    HEADER="Authorization: Bearer $HF_TOKEN"
fi

# Скачиваем с флагом -nv (No Verbose - убирает простыню)
wget -nv --header "$HEADER" -nc -O "$LORA_PATH/Qwen4Play_v2.safetensors" "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/Qwen4Play_v2.safetensors?download=true"

wget -nv --header "$HEADER" -nc -O "$LORA_PATH/Qwen_Snofs_1_3.safetensors" "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/Qwen_Snofs_1_3.safetensors?download=true"

wget -nv --header "$HEADER" -nc -O "$LORA_PATH/breast_slider_qwen_v1.safetensors" "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/breast_slider_qwen_v1.safetensors?download=true"

wget -nv --header "$HEADER" -nc -O "$LORA_PATH/hips_size_slider_v1.safetensors" "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/hips_size_slider_v1.safetensors?download=true"

# 5. ЗАПУСК БОТА
echo "🤖 Запуск бота в фоновом режиме..."
cd "$WORKSPACE"
nohup python bot.py > bot.log 2>&1 &

# 6. ЗАПУСК COMFYUI (ФИНАЛ)
# exec заменяет текущий процесс на ComfyUI, предотвращая перезагрузку контейнера
echo "⚡ Передаю управление скрипту /start.sh..."
chmod +x /start.sh
exec /start.sh
