"""Weekly training job for the occupancy forecast (FR-FCST-02).

Reads completed reservations through a read-only database role, builds hourly "was a slot
free" rows and fits a logistic regression per lot, vehicle type, weekday and hour. With
less than 4 weeks of history it trains on simulated arrivals instead and marks the model
as an estimate. Each run writes a versioned file and then points model.joblib at it.

    python -m forecast.train.train            # one run (FORECAST_DB_URL, FORECAST_MODEL_DIR)
"""

import argparse
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import joblib
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

from forecast.common import HISTORY_WEEKS_REQUIRED, ConstantModel
from forecast.train.observations import observations
from forecast.train.simulate import simulate_stays

TRAINING_WEEKS = 12
BASELINE_DAYS = 28
CURRENT = "model.joblib"

SLOTS_SQL = """
    SELECT s.lot_id, s.slot_type, count(*)
    FROM lots_slot s JOIN lots_lot l ON l.id = s.lot_id
    WHERE NOT l.is_archived
    GROUP BY s.lot_id, s.slot_type
"""
STAYS_SQL = """
    SELECT s.lot_id, s.slot_type, r.entry_time, r.exit_time
    FROM reservations_reservation r JOIN lots_slot s ON s.id = r.slot_id
    WHERE r.status = 'Completed' AND r.entry_time IS NOT NULL AND r.exit_time > %s
"""
FIRST_SQL = "SELECT min(exit_time) FROM reservations_reservation WHERE status = 'Completed'"


def fit(rows):
    labels = [free for _, free in rows]
    if len(set(labels)) < 2:
        return ConstantModel(1.0 if labels and labels[0] else 0.0)
    model = make_pipeline(DictVectorizer(), LogisticRegression(max_iter=1000, C=1.0))
    model.fit([f for f, _ in rows], labels)
    return model


def load_history(dsn, since):
    import psycopg

    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(SLOTS_SQL)
        slot_counts = {(lot, slot_type): n for lot, slot_type, n in cur.fetchall()}
        cur.execute(FIRST_SQL)
        (first,) = cur.fetchone()
        cur.execute(STAYS_SQL, (since,))
        stays = cur.fetchall()
    return slot_counts, first, stays


def train(slot_counts, first_completed, stays, now, tz, seed=2026):
    """Return the model bundle: the model plus whether it is the simulated estimate."""
    now = now.astimezone(tz)
    history = now - first_completed if first_completed else timedelta(0)
    estimate = history < timedelta(weeks=HISTORY_WEEKS_REQUIRED)
    if estimate:
        start_day = (now - timedelta(days=BASELINE_DAYS)).date()
        stays = simulate_stays(slot_counts, start_day, BASELINE_DAYS, tz, seed)
        start = datetime.combine(start_day, datetime.min.time(), tz)
        end = start + timedelta(days=BASELINE_DAYS)
    else:
        start, end = now - timedelta(weeks=TRAINING_WEEKS), now
        stays = [(lot, t, a.astimezone(tz), b.astimezone(tz)) for lot, t, a, b in stays]
    rows = observations(stays, slot_counts, start, end)
    return {
        "model": fit(rows),
        "estimate": estimate,
        "version": now.strftime("%Y%m%d%H%M%S"),
        "trained_at": now.isoformat(),
        "lots": sorted({lot for lot, _ in slot_counts}),
        "rows": len(rows),
    }


def save(bundle, model_dir):
    model_dir = Path(model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    versioned = model_dir / f"model-{bundle['version']}.joblib"
    joblib.dump(bundle, versioned)
    temporary = model_dir / f".{CURRENT}.tmp"
    shutil.copyfile(versioned, temporary)
    os.replace(temporary, model_dir / CURRENT)  # atomic, so the service never reads half a file
    return versioned


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dsn", default=os.environ.get("FORECAST_DB_URL"))
    parser.add_argument("--model-dir", default=os.environ.get("FORECAST_MODEL_DIR", "models"))
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args(argv)
    if not args.dsn:
        parser.error("set FORECAST_DB_URL or pass --dsn")
    tz = ZoneInfo(os.environ.get("FORECAST_TIME_ZONE", "Asia/Kolkata"))
    now = datetime.now(tz)
    slot_counts, first, stays = load_history(args.dsn, now - timedelta(weeks=TRAINING_WEEKS))
    bundle = train(slot_counts, first, stays, now, tz, args.seed)
    path = save(bundle, args.model_dir)
    kind = "baseline estimate" if bundle["estimate"] else "history"
    print(f"Trained {path.name} from {kind}: {bundle['rows']} rows, lots {bundle['lots']}")


if __name__ == "__main__":
    main()
