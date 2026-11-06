from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from vps import factories
from vps.accounts.models import User
from vps.lots.plan import build_lot_plan
from vps.reservations.models import Reservation

pytestmark = pytest.mark.django_db


def test_owner_sees_map_with_highlight(client):
    now = timezone.now()
    driver = factories.make_driver()
    lot = factories.make_lot(name="Owner Lot", slots={"TwoWheeler": 3, "Standard": 2})
    slot = lot.slots.get(code="TW-001")
    reservation = factories.make_reservation(
        driver,
        slot,
        now + timedelta(minutes=15),
        status=Reservation.Status.RESERVED,
    )
    plan = build_lot_plan(lot.slots.all())
    expected_row = plan.bay_for(slot.pk).row
    client.force_login(driver)

    response = client.get(reverse("reservations:slot_map", args=[reservation.booking_ref]))
    content = response.content.decode()

    assert response.status_code == 200
    assert f'bay--you">{slot.code}' in content or f">{slot.code}</text>" in content
    assert 'id="lot-route"' in content
    assert (
        f"Your slot: {slot.code}, row {expected_row} from the entry gate, {lot.name}" in content
    )


def test_other_driver_gets_404(client):
    now = timezone.now()
    owner = factories.make_driver()
    intruder = factories.make_driver()
    lot = factories.make_lot(slots={"Standard": 1})
    reservation = factories.make_reservation(
        owner,
        lot.slots.get(code="ST-001"),
        now + timedelta(minutes=10),
        status=Reservation.Status.RESERVED,
    )
    client.force_login(intruder)

    response = client.get(reverse("reservations:slot_map", args=[reservation.booking_ref]))
    assert response.status_code == 404


def test_staff_forbidden(client):
    now = timezone.now()
    driver = factories.make_driver()
    attendant = factories.make_staff(role=User.Role.ATTENDANT)
    lot = factories.make_lot(slots={"Standard": 1})
    reservation = factories.make_reservation(
        driver,
        lot.slots.get(code="ST-001"),
        now + timedelta(minutes=10),
        status=Reservation.Status.RESERVED,
    )
    client.force_login(attendant)

    response = client.get(reverse("reservations:slot_map", args=[reservation.booking_ref]))
    assert response.status_code == 403


def test_history_links_map_for_open_bookings_only(client):
    now = timezone.now()
    driver = factories.make_driver()
    lot = factories.make_lot(slots={"Standard": 4})
    reserved = factories.make_reservation(
        driver, lot.slots.get(code="ST-001"), now + timedelta(minutes=20), status="Reserved"
    )
    active = factories.make_reservation(
        driver,
        lot.slots.get(code="ST-002"),
        now - timedelta(minutes=20),
        status="Active",
        entry_time=now - timedelta(minutes=10),
    )
    completed = factories.make_reservation(
        driver,
        lot.slots.get(code="ST-003"),
        now - timedelta(hours=3),
        hours=1,
        status="Completed",
        entry_time=now - timedelta(hours=3),
        exit_time=now - timedelta(hours=2),
    )
    cancelled = factories.make_reservation(
        driver, lot.slots.get(code="ST-004"), now + timedelta(hours=3), status="Cancelled"
    )
    client.force_login(driver)

    content = client.get(reverse("reservations:history")).content.decode()
    assert f'href="{reverse("reservations:slot_map", args=[reserved.booking_ref])}"' in content
    assert f'href="{reverse("reservations:slot_map", args=[active.booking_ref])}"' in content
    assert f'href="{reverse("reservations:slot_map", args=[completed.booking_ref])}"' not in content
    assert f'href="{reverse("reservations:slot_map", args=[cancelled.booking_ref])}"' not in content


def test_confirmation_embeds_plan(client):
    now = timezone.now()
    driver = factories.make_driver()
    lot = factories.make_lot(slots={"Standard": 1})
    reservation = factories.make_reservation(
        driver,
        lot.slots.get(code="ST-001"),
        now + timedelta(minutes=20),
        status=Reservation.Status.RESERVED,
    )
    client.force_login(driver)

    response = client.get(reverse("reservations:confirmation", args=[reservation.booking_ref]))
    assert response.status_code == 200
    assert "bay--you" in response.content.decode()
