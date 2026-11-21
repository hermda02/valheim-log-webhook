FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends docker-cli docker.io \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /app/
COPY src /app/src

RUN pip install --no-cache-dir .

ENTRYPOINT ["valheim-log-webhook"]
