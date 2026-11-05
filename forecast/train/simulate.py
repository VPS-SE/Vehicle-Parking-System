"""Simulated arrivals for the baseline model, used until 4 weeks of history exist (FR-FCST-02).

Each slot is filled hour by hour with the chance below: high in the morning and evening
peaks, low at night, and lower at weekends. Consecutive busy hours of one slot become one
stay. Each lot and day also gets a demand level between 0.85 and 1.12, so on busy days the
peaks fill every slot. The same seed always gives the same stays.
"""

import random
from datetime import datetime, time, timedelta

# Chance that a slot is in use during each hour on a weekday; hours not listed are empty.
WEEKDAY_OCCUPANCY = {
    6: 0.2, 7: 0.4, 8: 0.7, 9: 0.9, 10: 0.92, 11: 0.85, 12: 0.7, 13: 0.65, 14: 0.6,
    15: 0.6, 16: 0.7, 17: 0.85, 18: 0.85, 19: 0.7, 20: 0.45, 21: 0.3, 22: 0.15,
}  # fmt: skip
WEEKEND_FACTOR = 0.6
DEMAND_RANGE = (0.85, 1.12)


def simulate_stays(slot_counts, start_day, days, tz, seed=2026):
    """Stays as (lot_id, slot_type, entry, exit) for each slot over the given days."""
    rng = random.Random(seed)
    stays = []
    for offset in range(days):
        day = start_day + timedelta(days=offset)
        factor = WEEKEND_FACTOR if day.weekday() >= 5 else 1.0
        demand = {lot: rng.uniform(*DEMAND_RANGE) for lot, _ in sorted(slot_counts)}
        for (lot_id, slot_type), count in sorted(slot_counts.items()):
            for _slot in range(count):
                entry = None
                for hour in range(24):
                    chance = WEEKDAY_OCCUPANCY.get(hour, 0) * factor * demand[lot_id]
                    busy = rng.random() < chance
                    moment = datetime.combine(day, time(hour), tz)
                    if busy and entry is None:
                        entry = moment
                    elif not busy and entry is not None:
                        stays.append((lot_id, slot_type, entry, moment))
                        entry = None
                if entry is not None:
                    stays.append((lot_id, slot_type, entry, datetime.combine(day, time(23), tz)))
    return stays
