FROM python:3.11-slim

# Atrof-muhit sozlamalari
ENV PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

# Tizim paketlari
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-dev \
    build-essential \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Ishchi papka
WORKDIR /code

# Requirements o'rnatish
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Butun loyihani copy qilish
COPY . .

# Muhim: Bot papkasi ichidagi faylni ishga tushirish
CMD ["python", "-m", "bot.bot"]

# Agar yuqoridagi ishlamasa, quyidagilardan birini sinab ko'ring:
# CMD ["python", "bot/bot.py"]
