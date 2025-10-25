FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV MPLBACKEND=Agg

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends     curl ca-certificates pandoc     libfreetype6 libpng-dev &&     rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY data ./data
COPY config ./config
COPY frontend ./frontend
COPY static ./static
COPY templates ./templates
COPY tests ./tests
COPY e2e.py ./
COPY analytics ./analytics

EXPOSE 8080
CMD ["sh", "-c", "gunicorn -k uvicorn.workers.UvicornWorker app.main:app -b 0.0.0.0:${PORT:-8080} --timeout 600"]
