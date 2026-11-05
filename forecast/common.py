"""Rules shared by the forecast service and its training job (FR-FCST-01, FR-FCST-02)."""

from datetime import datetime

# The slot types each vehicle type may use, as in the web application's allocation rules
# (Accessible slots need a permit, so they are left out of the general forecast).
VEHICLE_SLOT_TYPES = {
    "Car": ("Standard",),
    "TwoWheeler": ("TwoWheeler",),
    "EV": ("EV", "Standard"),
}
VEHICLE_TYPES = tuple(VEHICLE_SLOT_TYPES)

# Until this many weeks of completed reservations exist, the simulated baseline is used.
HISTORY_WEEKS_REQUIRED = 4


def band(probability: float) -> str:
    """FR-FCST-01: Low below 40%, Medium from 40% to 75%, High above 75%."""
    if probability < 0.40:
        return "Low"
    if probability <= 0.75:
        return "Medium"
    return "High"


def features(lot_id: int, vehicle_type: str, moment: datetime) -> dict:
    """The model's inputs for one lot, vehicle type and local arrival time."""
    return {
        "lot": str(lot_id),
        "vehicle_type": vehicle_type,
        "weekday": str(moment.weekday()),
        "hour": str(moment.hour),
        "lot_hour": f"{lot_id}:{moment.hour}",
        "weekend": float(moment.weekday() >= 5),
    }


class ConstantModel:
    """Used when every training row has the same answer, which logistic regression rejects.

    It lives here, not in the training script, so a pickled model loads in the service.
    """

    def __init__(self, probability):
        self.probability = probability

    def predict_proba(self, rows):
        return [[1 - self.probability, self.probability] for _ in rows]
