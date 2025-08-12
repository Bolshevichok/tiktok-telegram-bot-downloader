FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py database.py ./

RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app

USER botuser

CMD ["python", "bot.py"]
