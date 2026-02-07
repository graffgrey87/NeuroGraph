#!/bin/bash

# === НАСТРОЙКИ ===
WORKSPACE="/workspace"
COMFY_DIR="/workspace/ComfyUI"
LORA_PATH="$COMFY_DIR/models/loras/Qwen_Pack"
WC_PATH="$COMFY_DIR/wildcards"

echo "🚀 ЗАПУСК УСТАНОВКИ (NeuroGraph Final)..."

# 1. Библиотеки
pip install python-telegram-bot requests websocket-client > /dev/null 2>&1

# 2. Файлы (Бот и Workflow)
# Копируем из текущей папки (куда RunPod склонировал репо)
cp bot.py "$WORKSPACE/bot.py"
# Копируем workflow_api.json и другие json, если есть
cp *.json "$WORKSPACE/" 2>/dev/null

# 3. Wildcards (Копируем папку)
mkdir -p "$WC_PATH"
cp -r wildcards/* "$WC_PATH/" 2>/dev/null

# 4. ЛОРЫ (Скачиваем с Hugging Face)
mkdir -p "$LORA_PATH"
echo "⬇️ Скачивание LoRAs..."

# Настраиваем заголовок с токеном (если он есть в RunPod)
AUTH_HEADER=""
if [ ! -z "$HF_TOKEN" ]; then
  AUTH_HEADER="--header=Authorization: Bearer $HF_TOKEN"
fi

# === ТВОИ ССЫЛКИ ===
# Обрати внимание: ссылки в кавычках!

# Qwen4Play
wget $AUTH_HEADER -nc -O "$LORA_PATH/Qwen4Play_v2.safetensors" "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/Qwen4Play_v2.safetensors?download=true"

# Qwen Snofs
wget $AUTH_HEADER -nc -O "$LORA_PATH/Qwen_Snofs_1_3.safetensors" "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/Qwen_Snofs_1_3.safetensors?download=true"

# Breast Slider
wget $AUTH_HEADER -nc -O "$LORA_PATH/breast_slider_qwen_v1.safetensors" "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/breast_slider_qwen_v1.safetensors?download=true"

# Hips Slider
wget $AUTH_HEADER -nc -O "$LORA_PATH/hips_size_slider_v1.safetensors" "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/hips_size_slider_v1.safetensors?download=true"

# ===================

# 5. ЗАПУСК БОТА В ФОНЕ (FIX ЗАВИСАНИЯ)
echo "🤖 Запуск бота в фоновом режиме..."
cd "$WORKSPACE"

# Запускаем бота так, чтобы он не блокировал терминал
nohup python bot.py > bot.log 2>&1 &

echo "✅ Установка завершена! Бот работает. Запускаем ComfyUI..."
