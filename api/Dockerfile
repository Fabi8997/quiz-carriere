FROM python:3.12-slim

WORKDIR /app

# Dipendenze sistema (psycopg2 ha bisogno di libpq)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Dipendenze Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Codice applicazione
COPY . .

# Porta esposta (Fly.io usa $PORT)
EXPOSE 8080

# Avvio: legge $PORT da Fly.io, default 8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
