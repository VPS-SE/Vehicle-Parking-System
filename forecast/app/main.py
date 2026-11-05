"""Forecast service (FR-FCST-01): probability that an eligible slot is free on arrival.

uvicorn forecast.app.main:app --port 8001      # FORECAST_MODEL_DIR holds model.joblib
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

import joblib
from fastapi import FastAPI, HTTPException, Query

from forecast.common import band, features

MAX_AHEAD = timedelta(hours=24)

app = FastAPI(title="VPS forecast service", version="1")
_cache = {"mtime": None, "bundle": None}


def model_path() -> Path:
    return Path(os.environ.get("FORECAST_MODEL_DIR", "models")) / "model.joblib"


def current_model():
    """The latest trained model, reloaded when the weekly job replaces the file."""
    path = model_path()
    try:
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        return None
    if mtime != _cache["mtime"]:
        _cache["bundle"], _cache["mtime"] = joblib.load(path), mtime
    return _cache["bundle"]


@app.get("/v1/health")
def health():
    bundle = current_model()
    if bundle is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {
        "status": "ok",
        "model_version": bundle["version"],
        "trained_at": bundle["trained_at"],
        "estimate": bundle["estimate"],
    }


@app.get("/v1/forecast")
def forecast(
    lot_id: int,
    vehicle_type: Literal["Car", "TwoWheeler", "EV"],
    arrival: Annotated[datetime, Query(description="ISO 8601 with offset, up to 24 hours ahead")],
):
    if arrival.tzinfo is None:
        raise HTTPException(status_code=422, detail="arrival needs a time zone offset")
    tz = ZoneInfo(os.environ.get("FORECAST_TIME_ZONE", "Asia/Kolkata"))
    now = datetime.now(tz)
    if not now - timedelta(minutes=5) <= arrival <= now + MAX_AHEAD:
        raise HTTPException(status_code=422, detail="arrival must be within the next 24 hours")
    bundle = current_model()
    if bundle is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    if lot_id not in bundle["lots"]:
        raise HTTPException(status_code=422, detail="unknown lot")
    probability = float(
        bundle["model"].predict_proba([features(lot_id, vehicle_type, arrival.astimezone(tz))])[0][
            1
        ]
    )
    probability = min(max(probability, 0.0), 1.0)
    return {
        "probability": round(probability, 4),
        "band": band(probability),
        "estimate": bundle["estimate"],
        "model_version": bundle["version"],
    }
