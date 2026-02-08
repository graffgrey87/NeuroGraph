#!/bin/bash

# ПУТИ (ЖЕСТКО ЗАДАНЫ)
VENV_PYTHON="/workspace/venv/bin/python"
VENV_PIP="/workspace/venv/bin/pip"
L_PATH="/workspace/ComfyUI/models/loras"

# 1. ЖДЕМ СТАРТА
echo "⏳ Жду порт 3000..."
while ! wget -q --spider http://127.0.0.1:3000; do
  sleep 2
done
echo "✅ Порт 3000 доступен."

# 2. БИБЛИОТЕКИ
echo "📦 Ставлю библиотеки..."
$VENV_PIP install python-telegram-bot requests websocket-client > /dev/null 2>&1

# 3. НОДЫ
echo "🧩 Ставлю ноды..."
cd /workspace/ComfyUI/custom_nodes
[ ! -d "mikey_nodes" ] && git clone https://github.com/bash-j/mikey_nodes.git
[ ! -d "comfy-image-saver" ] && git clone https://github.com/giriss/comfy-image-saver.git
[ ! -d "ComfyUI-Custom-Scripts" ] && git clone https://github.com/pythongosssss/ComfyUI-Custom-Scripts.git

# 4. КАЧАЕМ ЛОРЫ (ТЕПЕРЬ ПОДРОБНО!)
echo "⬇️ НАЧИНАЮ ЗАГРУЗКУ ЛОР..."
mkdir -p "$L_PATH"

# Убрал -q, добавил --verbose и -O для гарантии имени
# Если файл не скачается - мы увидим ошибку в логе
wget --verbose -nc -O "$L_PATH/Qwen4Play_v2.safetensors" "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/Qwen4Play_v2.safetensors?download=true"
wget --verbose -nc -O "$L_PATH/Qwen_Snofs_1_3.safetensors" "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/Qwen_Snofs_1_3.safetensors?download=true"
wget --verbose -nc -O "$L_PATH/breast_slider_qwen_v1.safetensors" "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/breast_slider_qwen_v1.safetensors?download=true"
wget --verbose -nc -O "$L_PATH/hips_size_slider_v1.safetensors" "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/hips_size_slider_v1.safetensors?download=true"

# КОНТРОЛЬНЫЙ ВЫСТРЕЛ: ВЫВОДИМ СПИСОК ФАЙЛОВ В ЛОГ
echo "📂 ПРОВЕРКА ПАПКИ LORAS:"
ls -lh "$L_PATH"

# 5. КОПИРУЕМ БОТА
echo "🤖 Копирую файлы бота..."
# Используем прямой путь, так как git clone был в /workspace/installer
cp /workspace/installer/bot.py /workspace/bot.py
cp /workspace/installer/*.json /workspace/ 2>/dev/null
[ -d "/workspace/installer/wildcards" ] && cp -r "/workspace/installer/wildcards" "/workspace/ComfyUI/"

# 6. ПЕРЕЗАПУСК
echo "🔄 Рестарт..."
pkill -f "python main.py"
pkill -f "bot.py"
sleep 5

echo "🤖 Старт Бота..."
nohup $VENV_PYTHON /workspace/bot.py > /workspace/bot.log 2>&1 &

echo "🚀 Старт ComfyUI..."
cd /workspace/ComfyUI
$VENV_PYTHON main.py --listen 0.0.0.0 --port 3000
