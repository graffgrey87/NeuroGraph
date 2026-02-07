#!/bin/bash

# === НАСТРОЙКИ ===
WORKSPACE="/workspace"
COMFY_DIR="/workspace/ComfyUI"
LORA_PATH="$COMFY_DIR/models/loras/Qwen_Pack"
WC_PATH="$COMFY_DIR/wildcards"

echo "🚀 ЗАПУСК УСТАНОВКИ (Fix Wget)..."

# 1. Подготовка
pip install python-telegram-bot requests websocket-client > /dev/null 2>&1
cp bot.py "$WORKSPACE/bot.py"
cp *.json "$WORKSPACE/" 2>/dev/null

# 2. Wildcards
mkdir -p "$WC_PATH"
cp -r wildcards/* "$WC_PATH/" 2>/dev/null

# 3. ЛОРЫ (Прямая авторизация)
mkdir -p "$LORA_PATH"
echo "⬇️ Скачивание LoRAs..."

# Мы проверяем, есть ли токен. Если есть - используем заголовок.
# В этот раз пишем команду полностью, чтобы bash не путался.

if [ -z "$HF_TOKEN" ]; then
    echo "⚠️ HF_TOKEN не найден! Пробую качать без авторизации..."
    HEADER_CMD=""
else
    # Формируем заголовок правильно
    HEADER="Authorization: Bearer $HF_TOKEN"
fi

# Скачивание (Qwen4Play)
wget --header "$HEADER" -nc -O "$LORA_PATH/Qwen4Play_v2.safetensors" "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/Qwen4Play_v2.safetensors?download=true"

# Скачивание (Qwen Snofs)
wget --header "$HEADER" -nc -O "$LORA_PATH/Qwen_Snofs_1_3.safetensors" "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/Qwen_Snofs_1_3.safetensors?download=true"

# Скачивание (Breast Slider)
wget --header "$HEADER" -nc -O "$LORA_PATH/breast_slider_qwen_v1.safetensors" "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/breast_slider_qwen_v1.safetensors?download=true"

# Скачивание (Hips Slider)
wget --header "$HEADER" -nc -O "$LORA_PATH/hips_size_slider_v1.safetensors" "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/hips_size_slider_v1.safetensors?download=true"


# 4. ЗАПУСК БОТА
echo "🤖 Запуск бота в фоновом режиме..."
cd "$WORKSPACE"
nohup python bot.py > bot.log 2>&1 &

echo "✅ Установка завершена!"
