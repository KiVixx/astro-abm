FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV ASTRO_ABM_REPO_ROOT=/app
ENV PYTHONPATH=/app/astro_research/src:/app/src

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY sql ./sql
COPY scripts ./scripts
COPY astro_research ./astro_research
COPY .planning ./.planning

RUN pip install --no-cache-dir .

CMD ["astro-abm-data-completeness"]
