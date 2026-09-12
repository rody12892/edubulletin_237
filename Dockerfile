FROM python:3.11-slim

WORKDIR /app

# Empêcher l'écriture de bytecode et assurer le vidage régulier des logs
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Exposition explicite du port 8080
EXPOSE 8080

# Écoute stricte sur 0.0.0.0 et port 8080 (avec prise en compte dynamique de $PORT)
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}"]
