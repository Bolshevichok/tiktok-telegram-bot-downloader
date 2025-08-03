# Используем официальный Python образ
FROM python:3.11-slim

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY bot.py .

# Создаем пользователя для безопасности
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
USER botuser

# Запускаем бота
CMD ["python", "bot.py"]
