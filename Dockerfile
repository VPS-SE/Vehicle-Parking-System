FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 1000 app

COPY --chown=app:app . .
USER app

EXPOSE 8000
CMD ["gunicorn", "vps.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "8", "--timeout", "60"]
