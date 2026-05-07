FROM python:3.11-slim

# To'g'ri ENV formatlari
ENV PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

# Tizim paketlarini o'rnatish
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    python3-venv \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Ishchi papka
RUN mkdir -p /code
WORKDIR /code

# Requirements ni o'rnatish
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Kodni copy qilish
COPY . .

# Botni ishga tushirish
CMD ["python", "bot.py"]
