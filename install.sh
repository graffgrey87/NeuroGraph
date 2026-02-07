#!/bin/bash

# 1. НАСТРОЙКИ ПУТЕЙ (Строго по базе)
WORKSPACE="/workspace"
COMFY_DIR="/workspace/ComfyUI"
LORA_PATH="$COMFY_DIR/models/loras/Qwen_Pack"
# Путь для Mikey Nodes (корень ComfyUI)
WC_PATH="$COMFY_DIR/wildcards"

echo "🚀 УСТАНОВКА (GitHub версия)..."

# 2. Библиотеки
pip install python-telegram-bot requests websocket-client > /dev/null 2>&1

# 3. БОТ: Копируем из скачанной папки репо в корень
cp bot.py "$WORKSPACE/bot.py"

# 4. ВАЙЛДКАРДЫ: Копируем папку
echo "📂 Копирование Wildcards..."
mkdir -p "$WC_PATH"
# Флаг -r обязателен, чтобы скопировать всё содержимое папки
cp -r wildcards/* "$WC_PATH/" 2>/dev/null || echo "⚠️ Папка wildcards пуста"

# 5. ЛОРЫ: Качаем с Hugging Face (быстро и без токенов)
echo "⬇️ Скачивание LoRAs..."
mkdir -p "$LORA_PATH"

# Прямые ссылки (Qwen Pack)
wget -nc -O "$LORA_PATH/Qwen_Snofs_1_3.safetensors" "https://huggingface.co/Losiyp/Qwen_Snofs/resolve/main/Qwen_Snofs_1_3.safetensors?download=true"
wget -nc -O "$LORA_PATH/breast_slider_qwen_v1.safetensors" "https://huggingface.co/Losiyp/Qwen_Snofs/resolve/main/breast_slider_qwen_v1.safetensors?download=true"
wget -nc -O "$LORA_PATH/hips_size_slider_v1.safetensors" "https://huggingface.co/Losiyp/Qwen_Snofs/resolve/main/hips_size_slider_v1.safetensors?download=true"
wget -nc -O "$LORA_PATH/Qwen4Play_v2.safetensors" "https://huggingface.co/Losiyp/Qwen_Snofs/resolve/main/Qwen4Play_v2.safetensors?download=true"

# 6. ЗАПУСК
echo "🤖 Запуск бота..."
cd "$WORKSPACE"
python bot.py
