"""Turn parking stays into training rows: was an eligible slot free at each hour?"""

from collections import defaultdict
from datetime import datetime, timedelta

from forecast.common import VEHICLE_SLOT_TYPES, features

HOUR = timedelta(hours=1)


def _floor_hour(moment: datetime) -> datetime:
    return moment.replace(minute=0, second=0, microsecond=0)


def observations(stays, slot_counts, start: datetime, end: datetime):
    """Rows of (features, free) for each lot, vehicle type and hour in [start, end).

    stays: iterable of (lot_id, slot_type, entry, exit), aware datetimes in local time.
    slot_counts: {(lot_id, slot_type): number of slots}.
    An hour is sampled at its midpoint; free means at least one eligible slot was empty.
    """
    occupied = defaultdict(int)  # (lot, slot_type, hour start) -> slots in use at midpoint
    for lot_id, slot_type, entry, exit_ in stays:
        hour = _floor_hour(max(entry, start))
        while hour < min(exit_, end):
            if entry <= hour + HOUR / 2 < exit_:
                occupied[lot_id, slot_type, hour] += 1
            hour += HOUR

    lots = sorted({lot_id for lot_id, _ in slot_counts})
    rows = []
    hour = _floor_hour(start)
    while hour < end:
        midpoint = hour + HOUR / 2
        for lot_id in lots:
            for vehicle_type, slot_types in VEHICLE_SLOT_TYPES.items():
                total = sum(slot_counts.get((lot_id, t), 0) for t in slot_types)
                if not total:
                    continue
                used = sum(occupied[lot_id, t, hour] for t in slot_types)
                rows.append((features(lot_id, vehicle_type, midpoint), used < total))
        hour += HOUR
    return rows
