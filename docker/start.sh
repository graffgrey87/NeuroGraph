#!/bin/bash
set -e

# ==========================================
# 🚀 NeuroGraph — Entrypoint (start.sh)
# RunPod-совместимый стартовый скрипт
# ==========================================

echo "=========================================="
echo "🧠 NeuroGraph Container Starting..."
echo "   CUDA: $(nvcc --version 2>/dev/null | grep release | awk '{print $6}' || echo 'N/A')"
echo "   Python: $(python3 --version 2>&1)"
echo "=========================================="

export WORKSPACE=${WORKSPACE:-/workspace}
export VENV_PATH=/opt/venv
export PATH="${VENV_PATH}/bin:${PATH}"
export COMFYUI_PATH=${WORKSPACE}/ComfyUI

# ==========================================
# 1. NGINX
# ==========================================
start_nginx() {
    echo "🌐 Starting Nginx..."
    sed -i '/daemon off;/d' /etc/nginx/nginx.conf 2>/dev/null || true
    service nginx start 2>/dev/null || nginx 2>/dev/null || true
    echo "   Nginx ready."
}

# ==========================================
# 2. SSH
# ==========================================
setup_ssh() {
    echo "🔑 Setting up SSH..."

    if [[ ! -f /etc/ssh/ssh_host_rsa_key ]]; then
        ssh-keygen -t rsa -f /etc/ssh/ssh_host_rsa_key -q -N ''
    fi
    if [[ ! -f /etc/ssh/ssh_host_ed25519_key ]]; then
        ssh-keygen -t ed25519 -f /etc/ssh/ssh_host_ed25519_key -q -N ''
    fi

    if [[ -n "$PUBLIC_KEY" ]]; then
        mkdir -p ~/.ssh
        echo "$PUBLIC_KEY" >> ~/.ssh/authorized_keys
        chmod 700 ~/.ssh
        chmod 600 ~/.ssh/authorized_keys
    fi

    service ssh start 2>/dev/null || true
}

# ==========================================
# 3. JUPYTERLAB
# ==========================================
start_jupyter() {
    echo "📓 Starting JupyterLab on port 8888..."
    local jupyter_args="--ip=0.0.0.0 --port=8888 --no-browser --allow-root"

    if [[ -n "$ACCESS_PASSWORD" ]]; then
        jupyter_args="${jupyter_args} --ServerApp.token=${ACCESS_PASSWORD}"
    else
        jupyter_args="${jupyter_args} --ServerApp.token='' --ServerApp.password=''"
    fi

    nohup jupyter lab ${jupyter_args} --notebook-dir=${WORKSPACE} > /workspace/jupyter.log 2>&1 &
}

# ==========================================
# 4. ПОДГОТОВКА WORKSPACE (Network Volume)
# ==========================================
prepare_workspace() {
    echo "📦 Подготовка рабочей директории (${WORKSPACE})..."
    mkdir -p "${WORKSPACE}"

    # Обеспечиваем симлинк /workspace/venv -> /opt/venv (чтобы все старые скрипты работали)
    if [[ -d "${WORKSPACE}/venv" && ! -L "${WORKSPACE}/venv" ]]; then
        echo "⚠️ Обнаружен старый venv на Network Volume. Заменяем на быстрый образ cu130..."
        mv "${WORKSPACE}/venv" "${WORKSPACE}/venv_old_backup_$(date +%s)" 2>/dev/null || rm -rf "${WORKSPACE}/venv"
    fi
    ln -sf /opt/venv "${WORKSPACE}/venv"

    # Разворачиваем ComfyUI на Network Volume если его ещё нет
    if [[ ! -f "${COMFYUI_PATH}/main.py" ]]; then
        echo "⏳ ComfyUI не найден в ${WORKSPACE}, копируем базовую установку из образа..."
        rsync -a /opt/ComfyUI/ "${COMFYUI_PATH}/"
    else
        echo "✅ ComfyUI найден на Network Volume."
        # Досинхронизируем custom_nodes из образа если каких-то не хватает
        rsync -a --ignore-existing /opt/ComfyUI/custom_nodes/ "${COMFYUI_PATH}/custom_nodes/" 2>/dev/null || true
    fi

    # Гарантируем структуру папок под модели (200GB Network Volume)
    mkdir -p \
        "${COMFYUI_PATH}/models/diffusion_models" \
        "${COMFYUI_PATH}/models/text_encoders" \
        "${COMFYUI_PATH}/models/vae" \
        "${COMFYUI_PATH}/models/loras" \
        "${COMFYUI_PATH}/input" \
        "${WORKSPACE}/templates" \
        "${WORKSPACE}/wildcards"
}

# ==========================================
# 5. NEUROGRAPH POST-START (в фоне)
# ==========================================
start_neurograph() {
    echo "🤖 Запуск фонового скрипта NeuroGraph..."
    nohup bash /neurograph_startup.sh > /workspace/neurograph_startup.log 2>&1 &
}

# ==========================================
# 6. COMFYUI (foreground — удерживает контейнер)
# ==========================================
start_comfyui() {
    echo "🎨 Запуск ComfyUI на 0.0.0.0:3000..."
    cd "${COMFYUI_PATH}"

    local extra_args="${COMFYUI_EXTRA_ARGS:-}"

    exec python main.py \
        --listen 0.0.0.0 \
        --port 3000 \
        --enable-cors-header \
        ${extra_args}
}

# ==========================================
# MAIN EXECUTION
# ==========================================
start_nginx
setup_ssh
start_jupyter
prepare_workspace
start_neurograph

echo ""
echo "✅ Все фоновые службы инициализированы. Стартуем ComfyUI..."
echo ""

start_comfyui
