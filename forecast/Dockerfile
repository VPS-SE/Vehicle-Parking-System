FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

COPY forecast/requirements.txt forecast/requirements.txt
RUN pip install --no-cache-dir -r forecast/requirements.txt \
    && useradd --create-home --uid 1000 app \
    && mkdir -p /srv/models && chown app:app /srv/models

COPY --chown=app:app forecast forecast
USER app

ENV FORECAST_MODEL_DIR=/srv/models
EXPOSE 8001
CMD ["uvicorn", "forecast.app.main:app", "--host", "0.0.0.0", "--port", "8001"]
