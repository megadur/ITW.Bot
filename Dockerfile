FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ordner für Datenbank und Logs sicherstellen
RUN mkdir -p /app/data /app/logs

VOLUME ["/app/data", "/app/logs"]

CMD ["python", "-u", "bot.py"]
