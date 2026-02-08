#!/bin/bash

# 1. ЖДЕМ ЗАПУСКА СМЫШНИКОВА (ПОРТ 3000)
echo "⏳ Жду, пока ComfyUI ответит на порту 3000..."

# ИСПРАВЛЕНИЕ: Используем wget вместо netstat (так как netstat нет в системе)
# Мы пытаемся подключиться к локальному серверу. Пока он не ответит, ждем.
while ! wget -q --spider http://127.0.0.1:3000; do
  sleep 2
done

echo "✅ ComfyUI (Port 3000) ответил! Начинаю установку..."

# 2. СТАВИМ ЗАВИСИМОСТИ
pip install python-telegram-bot requests websocket-client > /dev/null 2>&1

# 3. НОДЫ
cd /workspace/ComfyUI/custom_nodes
[ ! -d "mikey_nodes" ] && git clone https://github.com/bash-j/mikey_nodes.git
[ ! -d "comfy-image-saver" ] && git clone https://github.com/giriss/comfy-image-saver.git
[ ! -d "ComfyUI-Custom-Scripts" ] && git clone https://github.com/pythongosssss/ComfyUI-Custom-Scripts.git

# 4. КАЧАЕМ ЛОРЫ
L_PATH="/workspace/ComfyUI/models/loras"
mkdir -p "$L_PATH"
# Твои ссылки
wget -q -nc -P "$L_PATH" "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/Qwen4Play_v2.safetensors?download=true"
wget -q -nc -P "$L_PATH" "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/Qwen_Snofs_1_3.safetensors?download=true"
wget -q -nc -P "$L_PATH" "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/breast_slider_qwen_v1.safetensors?download=true"
wget -q -nc -P "$L_PATH" "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/hips_size_slider_v1.safetensors?download=true"

# 5. КОПИРУЕМ БОТА ИЗ СКАЧАННОГО РЕПОЗИТОРИЯ
SCRIPT_DIR=$(dirname "$0")
cp "$SCRIPT_DIR/bot.py" /workspace/bot.py
cp "$SCRIPT_DIR/"*.json /workspace/ 2>/dev/null
# Если используешь wildcards
[ -d "$SCRIPT_DIR/wildcards" ] && cp -r "$SCRIPT_DIR/wildcards" "/workspace/ComfyUI/"

# 6. ПЕРЕЗАГРУЗКА ДЛЯ ПРИМЕНЕНИЯ (HIJACK)
echo "🔄 Рестарт Comfy..."
pkill -f "python main.py"
pkill -f "bot.py"
sleep 5

echo "🤖 Старт Бота..."
nohup python /workspace/bot.py > /workspace/bot.log 2>&1 &

echo "🚀 Старт ComfyUI..."
cd /workspace/ComfyUI
# Запускаем на 3000
python main.py --listen 0.0.0.0 --port 3000
