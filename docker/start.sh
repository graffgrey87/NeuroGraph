#!/bin/bash
set -e

# ==========================================
# 🚀 NeuroGraph — Entrypoint (start.sh)
# RunPod-совместимый стартовый скрипт
# ==========================================

echo "=========================================="
echo "🧠 NeuroGraph Container Starting..."
echo "   CUDA: $(nvcc --version 2>/dev/null | grep release | awk '{print $6}' || echo 'N/A')"
echo "   Python: $(python --version 2>&1)"
echo "   PyTorch CUDA: $(python -c 'import torch; print(torch.version.cuda)' 2>/dev/null || echo 'N/A')"
echo "=========================================="

# ── Переменные ──
export WORKSPACE=${WORKSPACE:-/workspace}
export VENV_PATH=${VENV_PATH:-/workspace/venv}
export COMFYUI_PATH=${COMFYUI_PATH:-/workspace/ComfyUI}
export PATH="${VENV_PATH}/bin:${PATH}"

# ==========================================
# 1. NGINX
# ==========================================
start_nginx() {
    echo "🌐 Starting Nginx..."
    service nginx start 2>/dev/null || true
}

# ==========================================
# 2. SSH
# ==========================================
setup_ssh() {
    echo "🔑 Setting up SSH..."

    # Генерируем ключи если нет
    if [[ ! -f /etc/ssh/ssh_host_rsa_key ]]; then
        ssh-keygen -t rsa -f /etc/ssh/ssh_host_rsa_key -q -N ''
    fi
    if [[ ! -f /etc/ssh/ssh_host_ed25519_key ]]; then
        ssh-keygen -t ed25519 -f /etc/ssh/ssh_host_ed25519_key -q -N ''
    fi

    # Публичный ключ от RunPod (если передан)
    if [[ -n "$PUBLIC_KEY" ]]; then
        mkdir -p ~/.ssh
        echo "$PUBLIC_KEY" >> ~/.ssh/authorized_keys
        chmod 700 ~/.ssh
        chmod 600 ~/.ssh/authorized_keys
    fi

    service ssh start 2>/dev/null || true
    echo "   SSH host keys:"
    for key in /etc/ssh/ssh_host_*_key.pub; do
        ssh-keygen -lf "$key" 2>/dev/null || true
    done
}

# ==========================================
# 3. JUPYTERLAB
# ==========================================
start_jupyter() {
    echo "📓 Starting JupyterLab..."
    local jupyter_args="--ip=0.0.0.0 --port=8888 --no-browser --allow-root"

    if [[ -n "$ACCESS_PASSWORD" ]]; then
        jupyter_args="${jupyter_args} --ServerApp.token=${ACCESS_PASSWORD}"
        echo "   JupyterLab started with password"
    else
        jupyter_args="${jupyter_args} --ServerApp.token='' --ServerApp.password=''"
        echo "   JupyterLab started without password"
    fi

    nohup jupyter lab ${jupyter_args} --notebook-dir=${WORKSPACE} > /workspace/jupyter.log 2>&1 &
}

# ==========================================
# 4. ПРОВЕРКА / SYNC VENV
# ==========================================
sync_workspace() {
    # Если venv нет в workspace (первый запуск с Network Volume)
    if [[ ! -d "${VENV_PATH}/bin" ]]; then
        echo "⏳ venv not found in workspace, syncing..."
        # Если venv был создан при сборке образа в другом месте
        if [[ -d "/opt/venv/bin" ]]; then
            cp -r /opt/venv ${VENV_PATH}
        else
            echo "⚠️ No venv source found, creating fresh..."
            python3.13 -m venv ${VENV_PATH}
            pip install --upgrade pip
            pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130
        fi
    fi

    # Если ComfyUI нет в workspace (первый запуск)
    if [[ ! -d "${COMFYUI_PATH}/main.py" ]] && [[ ! -f "${COMFYUI_PATH}/main.py" ]]; then
        echo "⏳ ComfyUI not found in workspace, syncing..."
        if [[ -d "/opt/ComfyUI" ]]; then
            rsync -a --ignore-existing /opt/ComfyUI/ ${COMFYUI_PATH}/
        else
            git clone https://github.com/comfyanonymous/ComfyUI.git ${COMFYUI_PATH}
            cd ${COMFYUI_PATH} && pip install -r requirements.txt
        fi
    fi
}

# ==========================================
# 5. NEUROGRAPH POST-START (фон)
# ==========================================
start_neurograph() {
    echo "🤖 Launching NeuroGraph startup in background..."
    nohup bash /neurograph_startup.sh > /workspace/neurograph_startup.log 2>&1 &
}

# ==========================================
# 6. COMFYUI (foreground — держит контейнер)
# ==========================================
start_comfyui() {
    echo "🎨 Starting ComfyUI on 0.0.0.0:3000..."
    cd ${COMFYUI_PATH}

    # Доп. аргументы из переменной окружения (опционально)
    local extra_args="${COMFYUI_EXTRA_ARGS:-}"

    exec python main.py \
        --listen 0.0.0.0 \
        --port 3000 \
        --enable-cors-header \
        ${extra_args}
}

# ==========================================
# MAIN
# ==========================================

start_nginx
setup_ssh
start_jupyter
sync_workspace
start_neurograph

echo ""
echo "✅ All services started. Launching ComfyUI..."
echo ""

start_comfyui
