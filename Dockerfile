FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends     curl ca-certificates pandoc &&     rm -rf /var/lib/apt/lists/*

COPY requirements-core.txt ./
RUN pip install --no-cache-dir -r requirements-core.txt

COPY app ./app
COPY data ./data
COPY config ./config
COPY frontend ./frontend
COPY templates ./templates
COPY tests ./tests

EXPOSE 8080
CMD ["sh", "-c", "gunicorn -k uvicorn.workers.UvicornWorker app.main:app -b 0.0.0.0:${PORT:-8080} --timeout 600"]
