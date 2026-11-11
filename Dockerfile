# Python 3.14 — mahalliy muhit bilan bir xil versiya (3.14.4 / image 3.14.x)
FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Xavfsizlik: bot root sifatida ishlamaydi
RUN groupadd --system app && useradd --system --gid app --home /app app

COPY pyproject.toml README.md ./
COPY bot ./bot
RUN pip install .

USER app

CMD ["python", "-m", "bot.main"]
