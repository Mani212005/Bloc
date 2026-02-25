FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Simple, explicit start command with full logging
CMD python -c "import sys; print('Python version:', sys.version); print('Working dir:', __import__('os').getcwd()); print('Files:', __import__('os').listdir('.')); print('Starting uvicorn...'); sys.stdout.flush()" && \
    uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --log-level info
