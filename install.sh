#!/bin/bash
# NeuroGraph Installer v15 (User Verified Links)

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
    
    if [ -f "$NODES_PATH/$DIR_NAME/requirements.txt" ]; then
        echo "📦 Ставлю зависимости для $DIR_NAME..."
        pip install -r "$NODES_PATH/$DIR_NAME/requirements.txt" > /dev/null 2>&1
    fi
}

# --- 2. УСТАНОВКА НОД (ТВОИ ССЫЛКИ) ---
cd "$NODES_PATH"

# Твои паки
install_node "https://github.com/bash-j/mikey_nodes.git" "mikey_nodes"
install_node "https://github.com/giriss/comfy-image-saver.git" "comfy-image-saver"

# База (на всякий случай, чтобы система понимала примитивы)
install_node "https://github.com/pythongosssss/ComfyUI-Custom-Scripts.git" "ComfyUI-Custom-Scripts"


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
if [ -d "/workspace/installer" ]; then
    cp /workspace/installer/bot.py "$WORKSPACE/bot.py"
    cp /workspace/installer/*.json "$WORKSPACE/" 2>/dev/null
    mkdir -p "$WC_PATH"
    cp -r /workspace/installer/wildcards/* "$WC_PATH/" 2>/dev/null
fi

pip install python-telegram-bot requests websocket-client > /dev/null 2>&1

cd "$WORKSPACE"
pkill -f "bot.py"
nohup python bot.py > /workspace/logs/bot.log 2>&1 &


# --- 5. ФИНАЛЬНЫЙ РЕСТАРТ ---
echo "🔄 Перезагружаю ComfyUI..."
pkill -f "python main.py"

echo "✅ [NeuroGraph] Установка завершена!"
