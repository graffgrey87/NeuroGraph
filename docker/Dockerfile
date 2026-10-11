# ==========================================
# 🐳 NeuroGraph Docker Image
# CUDA 13.0 + PyTorch cu130 + ComfyUI + Bot
# ==========================================

FROM nvidia/cuda:13.0.0-devel-ubuntu22.04

LABEL maintainer="graffgrey87"
LABEL description="NeuroGraph: ComfyUI + Telegram Bot for RunPod"

# ── Переменные окружения ──
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    SHELL=/bin/bash \
    WORKSPACE=/workspace \
    VENV_PATH=/workspace/venv \
    COMFYUI_PATH=/workspace/ComfyUI \
    TORCH_CUDA_ARCH_LIST="8.0;8.6;8.9;9.0" \
    PIP_PREFER_BINARY=1 \
    PIP_NO_CACHE_DIR=1

# ==========================================
# 1. СИСТЕМНЫЕ ПАКЕТЫ
# ==========================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Базовые
    bash curl wget git git-lfs ca-certificates \
    software-properties-common build-essential \
    # Сетевые / RunPod сервисы
    nginx openssh-server \
    # Утилиты
    aria2 htop nano tmux zip unzip rsync \
    # Python build-deps
    libssl-dev zlib1g-dev libbz2-dev libreadline-dev \
    libsqlite3-dev libncursesw5-dev libxml2-dev libxmlsec1-dev \
    libffi-dev liblzma-dev tk-dev \
    # Pillow deps
    libjpeg-dev libpng-dev libwebp-dev \
    && rm -rf /var/lib/apt/lists/*

# ==========================================
# 2. PYTHON 3.13 (deadsnakes PPA)
# ==========================================
RUN add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    python3.13 python3.13-venv python3.13-dev python3.13-distutils && \
    rm -rf /var/lib/apt/lists/* && \
    ln -sf /usr/bin/python3.13 /usr/bin/python3 && \
    ln -sf /usr/bin/python3.13 /usr/bin/python

# ==========================================
# 3. WORKSPACE + VENV + PYTORCH cu130
# ==========================================
RUN mkdir -p ${WORKSPACE} && \
    python3.13 -m venv ${VENV_PATH}

# Активируем venv для всех последующих RUN
ENV PATH="${VENV_PATH}/bin:${PATH}"

RUN pip install --upgrade pip setuptools wheel && \
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130

# ==========================================
# 4. COMFYUI
# ==========================================
RUN git clone https://github.com/comfyanonymous/ComfyUI.git ${COMFYUI_PATH} && \
    cd ${COMFYUI_PATH} && \
    pip install -r requirements.txt

# ==========================================
# 5. COMFYUI MANAGER
# ==========================================
RUN cd ${COMFYUI_PATH}/custom_nodes && \
    git clone --depth 1 https://github.com/Comfy-Org/ComfyUI-Manager.git && \
    cd ComfyUI-Manager && \
    if [ -f requirements.txt ]; then pip install -r requirements.txt; fi

# ==========================================
# 6. CUSTOM NODES (из install.sh)
# ==========================================
RUN cd ${COMFYUI_PATH}/custom_nodes && \
    git clone --depth 1 https://github.com/bash-j/mikey_nodes.git && \
    git clone --depth 1 https://github.com/giriss/comfy-image-saver.git && \
    git clone --depth 1 https://github.com/pythongosssss/ComfyUI-Custom-Scripts.git && \
    git clone --depth 1 https://github.com/ltdrdata/comfyui-inpaint-cropandstitch.git && \
    git clone --depth 1 https://github.com/StableLlama/ComfyUI-basic_data_handling.git

# Устанавливаем зависимости нод (если есть requirements.txt)
RUN for node_dir in ${COMFYUI_PATH}/custom_nodes/*/; do \
        if [ -f "${node_dir}requirements.txt" ]; then \
            echo "📦 Installing deps for $(basename ${node_dir})..." && \
            pip install -r "${node_dir}requirements.txt" || true; \
        fi; \
    done

# ==========================================
# 7. ЗАВИСИМОСТИ БОТА (python-telegram-bot, fastapi, etc.)
# ==========================================
RUN pip install \
    python-telegram-bot \
    requests \
    websocket-client \
    websockets \
    aiohttp \
    fastapi \
    uvicorn \
    Jinja2 \
    python-multipart \
    Pillow \
    jupyterlab \
    nvidia-ml-py

# ==========================================
# 8. SSH НАСТРОЙКА
# ==========================================
RUN mkdir -p /var/run/sshd && \
    echo "PermitRootLogin yes" >> /etc/ssh/sshd_config && \
    echo "PasswordAuthentication yes" >> /etc/ssh/sshd_config && \
    echo "root:neurograph" | chpasswd && \
    ssh-keygen -A

# ==========================================
# 9. NGINX (RunPod proxy)
# ==========================================
RUN echo "daemon off;" >> /etc/nginx/nginx.conf

# ==========================================
# 10. СОЗДАЁМ СТРУКТУРУ ДИРЕКТОРИЙ
# ==========================================
RUN mkdir -p \
    ${COMFYUI_PATH}/models/diffusion_models \
    ${COMFYUI_PATH}/models/text_encoders \
    ${COMFYUI_PATH}/models/vae \
    ${COMFYUI_PATH}/models/loras \
    ${COMFYUI_PATH}/input \
    ${WORKSPACE}/templates \
    ${WORKSPACE}/wildcards

# ==========================================
# 11. СКРИПТЫ ЗАПУСКА
# ==========================================
COPY docker/start.sh /start.sh
COPY docker/neurograph_startup.sh /neurograph_startup.sh
RUN chmod +x /start.sh /neurograph_startup.sh

# ==========================================
# 12. ПОРТЫ
# ==========================================
EXPOSE 3000 8081 8099 8888 22

# ==========================================
# 13. ЗАПУСК
# ==========================================
CMD ["/start.sh"]
