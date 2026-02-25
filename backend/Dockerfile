FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "set -x && echo '=== STARTING APP ===' && python -c 'import sys; print(sys.path); import app.main; print(\"Import OK\")' && echo '=== LAUNCHING UVICORN ===' && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
