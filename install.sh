#!/bin/bash

# === НАСТРОЙКИ ПУТЕЙ ===
WORKSPACE="/workspace"
COMFY_DIR="/workspace/ComfyUI"
LORA_PATH="$COMFY_DIR/models/loras/Qwen_Pack"
WC_PATH="$COMFY_DIR/wildcards" # Путь для Mikey Nodes

echo "🚀 ЗАПУСК УСТАНОВКИ (NeuroGraph Secure)..."

# 1. Библиотеки
pip install python-telegram-bot requests websocket-client > /dev/null 2>&1

# 2. ФАЙЛЫ: Копируем бота и ВСЕ json файлы (твои воркфлоу)
echo "📂 Копирование файлов..."
cp bot.py "$WORKSPACE/bot.py"
cp *.json "$WORKSPACE/" 2>/dev/null || echo "⚠️ JSON файлы (Workflow) не найдены!"

# 3. ВАЙЛДКАРДЫ
echo "📂 Установка Wildcards..."
mkdir -p "$WC_PATH"
cp -r wildcards/* "$WC_PATH/" 2>/dev/null || echo "⚠️ Папка wildcards пуста"

# 4. ЛОРЫ (С АВТОРИЗАЦИЕЙ)
echo "⬇️ Скачивание LoRAs..."
mkdir -p "$LORA_PATH"

# Проверка токена
if [ -z "$HF_TOKEN" ]; then
  echo "❌ ОШИБКА: Нет HF_TOKEN в настройках RunPod! Скачивание невозможно."
else
  # Скачиваем с заголовком авторизации
  wget --header "Authorization: Bearer $HF_TOKEN" -nc -O "$LORA_PATH/Qwen_Snofs_1_3.safetensors" "https://huggingface.co/Losiyp/Qwen_Snofs/resolve/main/Qwen_Snofs_1_3.safetensors?download=true"
  wget --header "Authorization: Bearer $HF_TOKEN" -nc -O "$LORA_PATH/breast_slider_qwen_v1.safetensors" "https://huggingface.co/Losiyp/Qwen_Snofs/resolve/main/breast_slider_qwen_v1.safetensors?download=true"
  wget --header "Authorization: Bearer $HF_TOKEN" -nc -O "$LORA_PATH/hips_size_slider_v1.safetensors" "https://huggingface.co/Losiyp/Qwen_Snofs/resolve/main/hips_size_slider_v1.safetensors?download=true"
  wget --header "Authorization: Bearer $HF_TOKEN" -nc -O "$LORA_PATH/Qwen4Play_v2.safetensors" "https://huggingface.co/Losiyp/Qwen_Snofs/resolve/main/Qwen4Play_v2.safetensors?download=true"
fi

# 5. ЗАПУСК
echo "🤖 Запуск бота..."
cd "$WORKSPACE"
python bot.py
