"""Forecast service and training job: FR-FCST-01, FR-FCST-02 (TC-35)."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from forecast.app import main
from forecast.common import ConstantModel, band, features
from forecast.train import train as trainer
from forecast.train.observations import observations
from forecast.train.simulate import simulate_stays

IST = ZoneInfo("Asia/Kolkata")
NOW = datetime(2026, 11, 5, 8, 0, tzinfo=IST)


class StubModel:
    """Returns the queued probabilities in order, as TC-35's stub model does."""

    def __init__(self, *probabilities):
        self.probabilities = list(probabilities)

    def predict_proba(self, rows):
        return [[0, self.probabilities.pop(0)] for _ in rows]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("FORECAST_MODEL_DIR", str(tmp_path))
    main._cache.update(mtime=None, bundle=None)
    return TestClient(main.app)


def install(tmp_path, model, estimate=True, lots=(1,), version="20261105000000"):
    trainer.save(
        {
            "model": model,
            "estimate": estimate,
            "version": version,
            "trained_at": NOW.isoformat(),
            "lots": list(lots),
            "rows": 0,
        },
        tmp_path,
    )


def ask(client, arrival, lot_id=1, vehicle_type="Car"):
    return client.get(
        "/v1/forecast",
        params={"lot_id": lot_id, "vehicle_type": vehicle_type, "arrival": arrival.isoformat()},
    )


@pytest.mark.parametrize(
    "p,expected",
    [
        (0.0, "Low"),
        (0.35, "Low"),
        (0.3999, "Low"),
        (0.40, "Medium"),
        (0.60, "Medium"),
        (0.75, "Medium"),
        (0.7501, "High"),
        (0.90, "High"),
        (1.0, "High"),
    ],
)
def test_bands(p, expected):
    assert band(p) == expected


def test_tc35_stub_model_bands_and_estimate_label(client, tmp_path):
    install(tmp_path, StubModel(0.35, 0.60, 0.90), estimate=True)
    soon = datetime.now(IST) + timedelta(hours=1)
    answers = [ask(client, soon + timedelta(hours=i)).json() for i in range(3)]
    assert [(a["probability"], a["band"], a["estimate"]) for a in answers] == [
        (0.35, "Low", True),
        (0.6, "Medium", True),
        (0.9, "High", True),
    ]


def test_input_errors_and_missing_model(client, tmp_path):
    soon = datetime.now(IST) + timedelta(hours=1)
    assert ask(client, soon).status_code == 503
    assert client.get("/v1/health").status_code == 503
    install(tmp_path, StubModel(0.5))
    assert client.get("/v1/health").json()["model_version"] == "20261105000000"
    assert ask(client, soon.replace(tzinfo=None)).status_code == 422
    assert ask(client, soon + timedelta(hours=25)).status_code == 422
    assert ask(client, soon, lot_id=99).status_code == 422
    assert ask(client, soon, vehicle_type="Bus").status_code == 422


def test_service_picks_up_a_retrained_model(client, tmp_path):
    soon = datetime.now(IST) + timedelta(hours=1)
    install(tmp_path, ConstantModel(0.2), version="1")
    assert ask(client, soon).json()["band"] == "Low"
    install(tmp_path, ConstantModel(0.9), estimate=False, version="2")
    main._cache["mtime"] = None  # file systems with coarse mtimes may not show the change
    answer = ask(client, soon).json()
    assert (answer["band"], answer["estimate"], answer["model_version"]) == ("High", False, "2")


def test_observations_sample_each_hour_midpoint():
    start = datetime(2026, 1, 5, 9, tzinfo=IST)
    stays = [
        (1, "Standard", start + timedelta(minutes=10), start + timedelta(minutes=50)),
        (1, "Standard", start + timedelta(hours=1), start + timedelta(hours=3)),
    ]
    rows = observations(
        stays, {(1, "Standard"): 1, (1, "EV"): 1}, start, start + timedelta(hours=3)
    )
    car = [free for f, free in rows if f["vehicle_type"] == "Car"]
    ev = [free for f, free in rows if f["vehicle_type"] == "EV"]
    assert car == [False, False, False]  # 09:30, 10:30 and 11:30 all taken
    assert ev == [True, True, True]  # the EV slot was always free
    assert not [f for f, _ in rows if f["vehicle_type"] == "TwoWheeler"]  # lot has none


def test_baseline_is_used_until_four_weeks_of_history():
    slots = {(1, "Standard"): 50}
    for first in (None, NOW - timedelta(weeks=3, days=6)):
        bundle = trainer.train(slots, first, [], NOW, IST)
        assert bundle["estimate"] is True and bundle["rows"] > 0
    busy = bundle["model"].predict_proba(
        [features(1, "Car", datetime(2026, 11, 9, 9, 30, tzinfo=IST))]
    )
    quiet = bundle["model"].predict_proba(
        [features(1, "Car", datetime(2026, 11, 9, 3, 30, tzinfo=IST))]
    )
    assert busy[0][1] < quiet[0][1]


def test_history_model_learns_the_busy_hour():
    slots = {(1, "Standard"): 1}
    stays = []
    day = (NOW - timedelta(weeks=10)).date()
    while day < NOW.date():
        entry = datetime.combine(day, time(10), IST)
        stays.append((1, "Standard", entry, entry + timedelta(hours=2)))
        day += timedelta(days=1)
    bundle = trainer.train(slots, NOW - timedelta(weeks=10), stays, NOW, IST)
    assert bundle["estimate"] is False
    model = bundle["model"]
    at = lambda h: model.predict_proba(
        [features(1, "Car", datetime(2026, 11, 6, h, 30, tzinfo=IST))]
    )[0][1]
    assert band(at(10)) == "Low"
    assert band(at(15)) == "High"


def test_simulation_is_repeatable():
    slots = {(1, "Standard"): 2, (2, "EV"): 1}
    day = datetime(2026, 1, 5).date()
    assert simulate_stays(slots, day, 3, IST, seed=7) == simulate_stays(slots, day, 3, IST, seed=7)
    assert simulate_stays(slots, day, 3, IST, seed=7) != simulate_stays(slots, day, 3, IST, seed=8)
