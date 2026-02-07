#!/bin/bash
# NeuroGraph Installer v12 (Nodes + Lora + Restart)

# --- НАСТРОЙКИ ---
WORKSPACE="/workspace"
COMFY_PATH="/workspace/ComfyUI"
NODES_PATH="$COMFY_PATH/custom_nodes"
LORA_PATH="$COMFY_PATH/models/loras/Qwen_Pack"
WC_PATH="$COMFY_PATH/wildcards"

echo "🎨 [NeuroGraph] Начинаю установку дополнений..."

# --- 1. ФУНКЦИЯ ДЛЯ УСТАНОВКИ НОД ---
install_node() {
    REPO_URL=$1
    DIR_NAME=$2
    if [ -d "$NODES_PATH/$DIR_NAME" ]; then
        echo "♻️ Обновляю $DIR_NAME..."
        rm -rf "$NODES_PATH/$DIR_NAME"
    fi
    echo "⬇️ Клонирую $DIR_NAME..."
    git clone "$REPO_URL" "$NODES_PATH/$DIR_NAME"
    
    # Если есть requirements.txt, ставим зависимости (тихо)
    if [ -f "$NODES_PATH/$DIR_NAME/requirements.txt" ]; then
        pip install -r "$NODES_PATH/$DIR_NAME/requirements.txt" > /dev/null 2>&1
    fi
}

# --- 2. УСТАНОВКА НОД ---
cd "$NODES_PATH"

# Нода 1: ComfyLiterals (Лечит ошибку String Literal / Positive)
install_node "https://github.com/idiap/ComfyLiterals.git" "ComfyLiterals"

# Нода 2: Mikey Nodes (Ты просил)
install_node "https://github.com/bash-j/mikey_nodes.git" "mikey_nodes"

# Нода 3: Image Saver (Ты просил)
install_node "https://github.com/giriss/ComfyUI-Image-Saver.git" "ComfyUI-Image-Saver"


# --- 3. СКАЧИВАНИЕ ЛОР ---
echo "⬇️ Проверка и скачивание Лор..."
mkdir -p "$LORA_PATH"

download_model() {
    if [ -z "$HF_TOKEN" ]; then
        wget -q -nc -O "$2" "$1"
    else
        wget -q --header "Authorization: Bearer $HF_TOKEN" -nc -O "$2" "$1"
    fi
}

download_model "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/Qwen4Play_v2.safetensors?download=true" "$LORA_PATH/Qwen4Play_v2.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/Qwen_Snofs_1_3.safetensors?download=true" "$LORA_PATH/Qwen_Snofs_1_3.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/breast_slider_qwen_v1.safetensors?download=true" "$LORA_PATH/breast_slider_qwen_v1.safetensors"
download_model "https://huggingface.co/datasets/AleksandrGrey87/My-Comfy-Pack/resolve/main/hips_size_slider_v1.safetensors?download=true" "$LORA_PATH/hips_size_slider_v1.safetensors"


# --- 4. ЗАПУСК БОТА ---
echo "🤖 Запуск бота..."
# Копируем файлы бота, если они скачались в installer
if [ -d "/workspace/installer" ]; then
    cp /workspace/installer/bot.py "$WORKSPACE/bot.py"
    cp /workspace/installer/*.json "$WORKSPACE/" 2>/dev/null
    mkdir -p "$WC_PATH"
    cp -r /workspace/installer/wildcards/* "$WC_PATH/" 2>/dev/null
fi

# Ставим либы для бота
pip install python-telegram-bot requests websocket-client > /dev/null 2>&1

cd "$WORKSPACE"
# Убиваем старого бота, если был
pkill -f "bot.py"
nohup python bot.py > /workspace/logs/bot.log 2>&1 &


# --- 5. ФИНАЛЬНЫЙ ШТРИХ: РЕСТАРТ ComfyUI ---
echo "🔄 Перезагружаю ComfyUI, чтобы он увидел новые ноды..."
# Убиваем процесс main.py. RunPod сам его перезапустит через 5 секунд.
pkill -f "python main.py"

echo "✅ [NeuroGraph] Готово! Через 10-15 секунд можно генерить."
