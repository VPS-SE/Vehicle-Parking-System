"""G1: staff search availability by vehicle type, or across every slot type (FR-SRCH-01)."""

from datetime import time, timedelta

import pytest
from django.utils import timezone

from vps.accounts.models import User
from vps.lots.models import Lot, Slot

pytestmark = pytest.mark.django_db


@pytest.fixture
def lot():
    lot = Lot.objects.create(name="G1", address="1 Road", opens_at=time(6), closes_at=time(23))
    Slot.objects.create(lot=lot, code="S1", slot_type="Standard", distance_rank=1)
    Slot.objects.create(lot=lot, code="T1", slot_type="TwoWheeler", distance_rank=2)
    Slot.objects.create(lot=lot, code="E1", slot_type="EV", distance_rank=3)
    return lot


def search(client, lot, **extra):
    day = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    start = day + timedelta(days=1, hours=10)
    params = {
        "lot": lot.pk,
        "start": start.strftime("%Y-%m-%dT%H:%M"),
        "end": (start + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M"),
        **extra,
    }
    return client.get("/reservations/search/", params)


@pytest.mark.parametrize("role", [User.Role.ATTENDANT, User.Role.ADMIN])
@pytest.mark.parametrize(
    "vehicle_type, expected", [("", 3), ("TwoWheeler", 1), ("EV", 2), ("Car", 1)]
)
def test_staff_search_counts_slots_for_the_vehicle_type(client, lot, role, vehicle_type, expected):
    client.force_login(User.objects.create_user(email="staff@example.com", role=role))
    response = search(client, lot, vehicle_type=vehicle_type)
    assert response.context["search_error"] == ""
    assert response.context["slot_count"] == expected
    assert response.context["confirm_url"] == ""


def test_driver_still_needs_one_of_their_vehicles(client, lot):
    client.force_login(User.objects.create_user(email="d@example.com"))
    response = search(client, lot)
    assert response.context["slot_count"] is None
    assert "one of your vehicles" in response.context["search_error"]
