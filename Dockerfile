FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 1000 app

COPY --chown=app:app . .
RUN DJANGO_SECRET_KEY=build-only python manage.py collectstatic --noinput
USER app

EXPOSE 8000
# GUNICORN_WORKERS bounds the database connections (one per worker).
ENV GUNICORN_WORKERS=8
CMD ["sh", "-c", "exec gunicorn vps.wsgi:application --bind 0.0.0.0:8000 --workers \"$GUNICORN_WORKERS\" --timeout 60"]
