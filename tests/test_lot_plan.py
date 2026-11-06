import random
from itertools import pairwise
from types import SimpleNamespace

from vps.lots.plan import build_lot_plan


def make_slots(mix):
    prefixes = {"TwoWheeler": "TW", "Standard": "ST", "EV": "EV", "Accessible": "AC"}
    slots = []
    pk = 1
    for slot_type, count in mix.items():
        for rank in range(1, count + 1):
            slots.append(
                SimpleNamespace(
                    pk=pk,
                    code=f"{prefixes[slot_type]}-{rank:03d}",
                    slot_type=slot_type,
                    distance_rank=rank,
                )
            )
            pk += 1
    return slots


def intersects(a, b):
    return not (
        a.x + a.w <= b.x
        or b.x + b.w <= a.x
        or a.y + a.h <= b.y
        or b.y + b.h <= a.y
    )


def test_every_slot_placed_once():
    slots = make_slots({"TwoWheeler": 200, "Standard": 80, "EV": 8, "Accessible": 4})
    plan = build_lot_plan(slots)
    assert len(plan.bays) == 292
    assert len({bay.slot_id for bay in plan.bays}) == 292


def test_bays_do_not_overlap_and_fit():
    slots = make_slots({"TwoWheeler": 200, "Standard": 80, "EV": 8, "Accessible": 4})
    plan = build_lot_plan(slots)
    for i, bay in enumerate(plan.bays):
        assert 0 <= bay.x
        assert 0 <= bay.y
        assert bay.x + bay.w <= plan.width
        assert bay.y + bay.h <= plan.height
        for other in plan.bays[i + 1 :]:
            assert not intersects(bay, other)


def test_zone_order_from_gate():
    slots = make_slots({"TwoWheeler": 8, "Standard": 8, "EV": 4, "Accessible": 4})
    plan = build_lot_plan(slots)
    zones = {
        "Accessible": [bay for bay in plan.bays if bay.slot_type == "Accessible"],
        "EV": [bay for bay in plan.bays if bay.slot_type == "EV"],
        "TwoWheeler": [bay for bay in plan.bays if bay.slot_type == "TwoWheeler"],
        "Standard": [bay for bay in plan.bays if bay.slot_type == "Standard"],
    }
    assert min(bay.y for bay in zones["Accessible"]) > max(bay.y + bay.h for bay in zones["EV"])
    assert min(bay.y for bay in zones["EV"]) > max(bay.y + bay.h for bay in zones["TwoWheeler"])
    assert min(bay.y for bay in zones["TwoWheeler"]) > max(
        bay.y + bay.h for bay in zones["Standard"]
    )


def test_lower_rank_not_farther():
    slots = make_slots({"TwoWheeler": 200, "Standard": 80, "EV": 8, "Accessible": 4})
    plan = build_lot_plan(slots)
    by_slot = {slot.pk: slot for slot in slots}
    by_type = {}
    for bay in plan.bays:
        by_type.setdefault(bay.slot_type, []).append(bay)
    for bays in by_type.values():
        for bay in bays:
            for other in bays:
                if by_slot[bay.slot_id].distance_rank < by_slot[other.slot_id].distance_rank:
                    assert bay.row <= other.row


def test_deterministic():
    slots = make_slots({"TwoWheeler": 200, "Standard": 80, "EV": 8, "Accessible": 4})
    shuffled = list(slots)
    random.Random(7).shuffle(shuffled)
    assert build_lot_plan(slots) == build_lot_plan(shuffled)


def test_empty_lot():
    plan = build_lot_plan([])
    assert plan.bays == ()
    assert plan.height >= 90


def test_route_starts_at_entry_ends_at_bay():
    slots = make_slots({"TwoWheeler": 10, "Standard": 4, "EV": 2, "Accessible": 2})
    plan = build_lot_plan(slots)
    bay = plan.bays[0]
    route = plan.route_to(bay.slot_id)
    assert route[0] == plan.entry
    assert route[-1] == (bay.cx, bay.cy)
    for (x1, y1), (x2, y2) in pairwise(route):
        assert x1 == x2 or y1 == y2
    for x, y in route:
        assert 0 <= x <= plan.width
        assert 0 <= y <= plan.height


def test_unknown_slot():
    plan = build_lot_plan(make_slots({"Standard": 4}))
    assert plan.bay_for(999) is None
    assert plan.route_to(999) == ()


def _segment_crosses(bay, p, q):
    """True if the axis-aligned segment p-q passes through the inside of the bay."""
    (x1, y1), (x2, y2) = p, q
    left, right = sorted((x1, x2))
    top, bottom = sorted((y1, y2))
    return left < bay.x + bay.w and right > bay.x and top < bay.y + bay.h and bottom > bay.y


def test_route_drives_along_lanes_not_through_bays():
    slots = make_slots({"TwoWheeler": 200, "Standard": 80, "EV": 8, "Accessible": 4})
    plan = build_lot_plan(slots)
    for target in plan.bays:
        route = plan.route_to(target.slot_id)
        # The last leg turns into the target bay; every leg before it must stay on lanes.
        for p, q in pairwise(route[:-1]):
            for bay in plan.bays:
                assert not _segment_crosses(bay, p, q), (target.code, bay.code, p, q)
        # The final leg may enter only the target bay.
        for bay in plan.bays:
            if bay.slot_id != target.slot_id:
                assert not _segment_crosses(bay, route[-2], route[-1]), (target.code, bay.code)
