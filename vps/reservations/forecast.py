"""Client for the forecast service (FR-FCST-01, FR-FCST-03).

Search must never wait on the forecast: any error, bad answer or reply slower than
FORECAST_TIMEOUT counts as "not available".
"""

import json
import logging
from datetime import timedelta
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger("vps.forecast")

MAX_AHEAD = timedelta(hours=24)
BANDS = {"Low", "Medium", "High"}


def get_forecast(lot_id, vehicle_type, arrival):
    """The service's answer as {percent, band, estimate}, or None if it is unavailable."""
    if not settings.FORECAST_URL:
        return None
    query = urlencode(
        {"lot_id": lot_id, "vehicle_type": vehicle_type, "arrival": arrival.isoformat()}
    )
    try:
        with urlopen(
            f"{settings.FORECAST_URL}/v1/forecast?{query}", timeout=settings.FORECAST_TIMEOUT
        ) as response:
            data = json.load(response)
        probability = float(data["probability"])
        if not 0 <= probability <= 1 or data["band"] not in BANDS:
            raise ValueError("forecast answer out of range")
    except (URLError, TimeoutError, OSError, ValueError, KeyError, TypeError) as error:
        logger.warning("Forecast not available: %s", error)
        return None
    return {
        "percent": round(probability * 100),
        "band": data["band"],
        "estimate": bool(data.get("estimate")),
    }


def forecast_panel(lot, vehicle_type, arrival, now=None):
    """What the search page shows: a forecast, a reason there is none, or not available."""
    now = now or timezone.now()
    if vehicle_type is None:
        return {"message": "Choose a vehicle type to see the forecast."}
    if not now - timedelta(minutes=5) <= arrival <= now + MAX_AHEAD:
        return {"message": "The forecast covers arrivals in the next 24 hours."}
    forecast = get_forecast(lot.pk, vehicle_type, arrival)
    if forecast is None:
        return {"message": "Forecast not available"}
    return forecast
