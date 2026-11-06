"""FR-LOTMAP-01: deterministic parking-lot plan geometry."""

from collections.abc import Iterable
from dataclasses import dataclass, field

from vps.lots.models import Slot

WIDTH = 1000

_DRIVEWAY_X = 70
_BAYS_X = 90
_RIGHT_MARGIN = 20
_TWO_WHEELER_SIZE = (20, 44)
_CAR_SIZE = (40, 70)
_AISLE_HEIGHT = 60
_GATE_BAND_HEIGHT = 90
_AISLE_X = _BAYS_X
_AISLE_W = WIDTH - _BAYS_X - _RIGHT_MARGIN
_ZONE_ORDER = ("Accessible", "EV", "TwoWheeler", "Standard")
_ZONE_INDEX = {slot_type: index for index, slot_type in enumerate(_ZONE_ORDER)}


@dataclass(frozen=True)
class Bay:
    slot_id: int
    code: str
    slot_type: str
    row: int
    x: int
    y: int
    w: int
    h: int

    @property
    def cx(self) -> int:
        return self.x + self.w // 2

    @property
    def cy(self) -> int:
        return self.y + self.h // 2


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int


@dataclass(frozen=True)
class LotPlan:
    width: int
    height: int
    bays: tuple[Bay, ...]
    aisles: tuple[Rect, ...]
    entry: tuple[int, int]
    exit: tuple[int, int]
    _by_slot: dict[int, Bay] = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        object.__setattr__(self, "_by_slot", {bay.slot_id: bay for bay in self.bays})

    def bay_for(self, slot_id) -> Bay | None:
        return self._by_slot.get(slot_id)

    def route_to(self, slot_id) -> tuple[tuple[int, int], ...]:
        bay = self.bay_for(slot_id)
        if bay is None:
            return ()
        lane_y = self._lane_y(bay)
        points = [self.entry, (self.entry[0], lane_y), (bay.cx, lane_y), (bay.cx, bay.cy)]
        route = []
        for point in points:
            if not route or route[-1] != point:
                route.append(point)
        return tuple(route)

    def _lane_y(self, bay: Bay) -> int:
        """Centre line of the lane the bay opens onto: an aisle touching it, else the gate band."""
        gate_band = Rect(x=0, y=self.height - _GATE_BAND_HEIGHT, w=self.width, h=_GATE_BAND_HEIGHT)
        for lane in (*self.aisles, gate_band):
            if lane.y == bay.y + bay.h or lane.y + lane.h == bay.y:
                return lane.y + lane.h // 2
        return gate_band.y + gate_band.h // 2


def _slot_size(slot_type: str) -> tuple[int, int]:
    if slot_type == Slot.SlotType.TWO_WHEELER:
        return _TWO_WHEELER_SIZE
    return _CAR_SIZE


def build_lot_plan(slots: Iterable[Slot]) -> LotPlan:
    ordered = sorted(
        slots,
        key=lambda slot: (
            _ZONE_INDEX.get(slot.slot_type, len(_ZONE_INDEX)),
            slot.distance_rank,
            slot.code,
        ),
    )
    row_number = 0
    rows_in_zone = 0
    y_up = 0
    current_zone = None
    current_type = None
    current_size = _CAR_SIZE
    row_slots = []
    raw_bays = []
    raw_aisles = []

    def add_aisle():
        nonlocal y_up
        raw_aisles.append(Rect(x=_AISLE_X, y=y_up, w=_AISLE_W, h=_AISLE_HEIGHT))
        y_up += _AISLE_HEIGHT

    def flush_row():
        nonlocal row_number, rows_in_zone, y_up, row_slots
        if not row_slots:
            return
        row_number += 1
        rows_in_zone += 1
        slot_w, slot_h = current_size
        for index, slot in enumerate(row_slots):
            raw_bays.append(
                Bay(
                    slot_id=slot.pk,
                    code=slot.code,
                    slot_type=slot.slot_type,
                    row=row_number,
                    x=_BAYS_X + index * slot_w,
                    y=y_up,
                    w=slot_w,
                    h=slot_h,
                )
            )
        y_up += slot_h
        row_slots = []
        if rows_in_zone % 2 == 0:
            add_aisle()

    for slot in ordered:
        zone = _ZONE_INDEX.get(slot.slot_type, len(_ZONE_INDEX))
        size = _slot_size(slot.slot_type)
        if current_zone is None:
            current_zone = zone
            current_type = slot.slot_type
            current_size = size
        elif zone != current_zone:
            flush_row()
            add_aisle()
            rows_in_zone = 0
            current_zone = zone
            current_type = slot.slot_type
            current_size = size

        per_row = (WIDTH - _BAYS_X - _RIGHT_MARGIN) // current_size[0]
        if row_slots and (slot.slot_type != current_type or len(row_slots) >= per_row):
            flush_row()
            current_type = slot.slot_type
            current_size = size
            per_row = (WIDTH - _BAYS_X - _RIGHT_MARGIN) // current_size[0]

        row_slots.append(slot)
        if len(row_slots) >= per_row:
            flush_row()

    flush_row()

    height = max(_GATE_BAND_HEIGHT, _GATE_BAND_HEIGHT + y_up)
    bays = tuple(
        Bay(
            slot_id=bay.slot_id,
            code=bay.code,
            slot_type=bay.slot_type,
            row=bay.row,
            x=bay.x,
            y=height - _GATE_BAND_HEIGHT - bay.y - bay.h,
            w=bay.w,
            h=bay.h,
        )
        for bay in raw_bays
    )
    aisles = tuple(
        Rect(
            x=rect.x,
            y=height - _GATE_BAND_HEIGHT - rect.y - rect.h,
            w=rect.w,
            h=rect.h,
        )
        for rect in raw_aisles
    )
    return LotPlan(
        width=WIDTH,
        height=height,
        bays=bays,
        aisles=aisles,
        entry=(35, height - 20),
        exit=(WIDTH - 35, height - 20),
    )
