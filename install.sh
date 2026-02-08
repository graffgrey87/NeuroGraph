#!/bin/bash

# ПУТИ
VENV_PYTHON="/workspace/venv/bin/python"
VENV_PIP="/workspace/venv/bin/pip"
L_PATH="/workspace/ComfyUI/models/loras"

# 1. ЖДЕМ ПОРТ 3000
echo "⏳ Жду порт 3000..."
while ! wget -q --spider http://127.0.0.1:3000; do
  sleep 2
done
echo "✅ Порт 3000 активен."

# 2. БИБЛИОТЕКИ
echo "📦 Ставлю библиотеки..."
$VENV_PIP install python-telegram-bot requests websocket-client > /dev/null 2>&1

# 3. НОДЫ
echo "🧩 Ставлю ноды..."
cd /workspace/ComfyUI/custom_nodes
[ ! -d "mikey_nodes" ] && git clone https://github.com/bash-j/mikey_nodes.git
[ ! -d "comfy-image-saver" ] && git clone https://github.com/giriss/comfy-image-saver.git
[ ! -d "ComfyUI-Custom-Scripts" ] && git clone https://github.com/pythongosssss/ComfyUI-Custom-Scripts.git

# 4. КАЧАЕМ ЛОРЫ (С ПОДРОБНЫМ ЛОГОМ)
echo "⬇️ Качаю Лоры..."
mkdir -p "$L_PATH"

download_model() {
    url="$1"
    file="$2"
    echo "---------------------------------------------------"
    echo "📥 Скачиваю: $file"
    
    if [ -z "$HF_TOKEN" ]; then
        echo "⚠️ HF_TOKEN не найден в переменных! Пробую качать без пароля..."
        # Убрал -q, чтобы видеть ошибки
        wget -nc -O "$L_PATH/$file" "$url"
    else
        echo "🔒 Использую HF_TOKEN для авторизации..."
        # Убрал -q, добавил хедер
        wget --header "Authorization: Bearer $HF_TOKEN" -nc -O "$L_PATH/$file" "$url"
    fi
}

# Список файлов
download_model "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/Qwen4Play_v2.safetensors?download=true" "Qwen4Play_v2.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/Qwen_Snofs_1_3.safetensors?download=true" "Qwen_Snofs_1_3.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/breast_slider_qwen_v1.safetensors?download=true" "breast_slider_qwen_v1.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/hips_size_slider_v1.safetensors?download=true" "hips_size_slider_v1.safetensors"

echo "---------------------------------------------------"
echo "📂 ИТОГОВАЯ ПРОВЕРКА ПАПКИ (Размер не должен быть 0):"
ls -lh "$L_PATH"
echo "---------------------------------------------------"

# 5. КОПИРУЕМ БОТА
echo "🤖 Копирую бота..."
cp /workspace/installer/bot.py /workspace/bot.py
cp /workspace/installer/*.json /workspace/ 2>/dev/null
[ -d "/workspace/installer/wildcards" ] && cp -r "/workspace/installer/wildcards" "/workspace/ComfyUI/"

# 6. ПЕРЕЗАПУСК
echo "🔄 Убиваю процессы..."
pkill -f "python main.py"
pkill -f "bot.py"
sleep 5

echo "🤖 Старт Бота..."
nohup $VENV_PYTHON /workspace/bot.py > /workspace/bot.log 2>&1 &

echo "🚀 Старт ComfyUI..."
cd /workspace/ComfyUI
$VENV_PYTHON main.py --listen 0.0.0.0 --port 3000
