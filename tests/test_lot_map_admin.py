from datetime import timedelta
from urllib.parse import urlencode

import pytest
from django.urls import reverse
from django.utils import timezone

from vps import factories
from vps.accounts.models import User
from vps.lots.models import Lot
from vps.reservations.models import Reservation

pytestmark = pytest.mark.django_db


def _admin_client(client):
    user = User.objects.create_user(email="admin.map@example.com", role=User.Role.ADMIN)
    client.force_login(user)
    return client


def test_admin_sees_states(client):
    now = timezone.now()
    admin_client = _admin_client(client)
    lot = factories.make_lot(slots={"Standard": 5})
    driver = factories.make_driver()

    factories.make_reservation(
        driver,
        lot.slots.get(code="ST-001"),
        now - timedelta(minutes=30),
        hours=2,
        status=Reservation.Status.ACTIVE,
    )
    factories.make_reservation(
        driver,
        lot.slots.get(code="ST-002"),
        now - timedelta(minutes=15),
        hours=2,
        status=Reservation.Status.RESERVED,
    )
    from django.db.backends.postgresql.psycopg_any import DateTimeTZRange

    from vps.lots.models import SlotBlock

    SlotBlock.objects.create(
        slot=lot.slots.get(code="ST-003"),
        period=DateTimeTZRange(now - timedelta(minutes=5), now + timedelta(minutes=25)),
        reason="Work",
    )

    response = admin_client.get(reverse("lots:map"), {"lot": lot.pk})
    content = response.content.decode()
    assert response.status_code == 200
    for state in ("occupied", "reserved", "blocked", "free"):
        assert f"bay--{state}" in content


def test_search_switches_lot_and_highlights(client):
    now = timezone.now()
    admin_client = _admin_client(client)
    first = factories.make_lot(name="First Lot", slots={"Standard": 1})
    second = factories.make_lot(name="Second Lot", slots={"Standard": 1})
    driver = factories.make_driver()
    driver.full_name = "Driver Map Name"
    driver.save(update_fields=["full_name"])
    parked = factories.make_reservation(
        driver,
        second.slots.get(code="ST-001"),
        now - timedelta(minutes=20),
        status=Reservation.Status.ACTIVE,
        entry_time=now - timedelta(minutes=10),
        vehicle_reg_no="KA05DM0001",
    )

    response = admin_client.get(reverse("lots:map"), {"lot": first.pk, "q": "ka05dm0001"})
    content = response.content.decode()
    assert response.status_code == 200
    assert "Second Lot" in content
    assert "bay--you" in content
    assert parked.booking_ref in content
    assert "Driver Map Name" in content
    assert "KA05DM0001" in content


def test_search_not_parked(client):
    admin_client = _admin_client(client)
    factories.make_lot(slots={"Standard": 1})

    response = admin_client.get(reverse("lots:map"), {"q": "KA05DM0001"})
    assert response.status_code == 200
    assert "KA05DM0001 is not parked in any lot right now." in response.content.decode()


def test_slot_detail(client):
    now = timezone.now()
    admin_client = _admin_client(client)
    lot = factories.make_lot(slots={"Standard": 1})
    driver = factories.make_driver()
    parked = factories.make_reservation(
        driver,
        lot.slots.get(code="ST-001"),
        now - timedelta(minutes=30),
        status=Reservation.Status.ACTIVE,
        entry_time=now - timedelta(minutes=15),
        vehicle_reg_no="KA05DM0001",
    )

    response = admin_client.get(reverse("lots:map"), {"lot": lot.pk, "slot": parked.slot_id})
    content = response.content.decode()
    assert response.status_code == 200
    assert parked.booking_ref in content
    assert "KA05DM0001" in content


def test_htmx_returns_panel_only(client):
    admin_client = _admin_client(client)
    lot = factories.make_lot(slots={"Standard": 1})

    response = admin_client.get(
        reverse("lots:map"), {"lot": lot.pk}, headers={"HX-Request": "true"}
    )
    content = response.content.decode()
    assert response.status_code == 200
    assert "<header>" not in content
    assert 'id="lot-map-panel"' in content


def test_archived_lot_hidden(client):
    admin_client = _admin_client(client)
    archived = factories.make_lot(name="Archived Lot", slots={"Standard": 1})
    archived.is_archived = True
    archived.save(update_fields=["is_archived"])
    first_active = factories.make_lot(name="AAA Active", slots={"Standard": 1})
    factories.make_lot(name="BBB Active", slots={"Standard": 1})

    response = admin_client.get(reverse("lots:map"), {"lot": archived.pk})
    content = response.content.decode()
    assert response.status_code == 200
    assert "Archived Lot" not in content
    assert f'value="{first_active.pk}" selected' in content


def test_empty_lot(client):
    admin_client = _admin_client(client)
    empty = Lot.objects.create(name="Empty Lot", address="1 Empty", opens_at="06:00", closes_at="22:00")

    response = admin_client.get(reverse("lots:map"), {"lot": empty.pk})
    assert response.status_code == 200
    assert "This lot has no slots yet." in response.content.decode()


def test_access(client):
    lot = factories.make_lot(slots={"Standard": 1})
    url = reverse("lots:map") + "?" + urlencode({"lot": lot.pk})

    assert client.get(url).status_code == 302
    assert "next=" in client.get(url).url

    driver = factories.make_driver()
    client.force_login(driver)
    assert client.get(url).status_code == 403

    client.force_login(factories.make_staff(role=User.Role.ATTENDANT))
    assert client.get(url).status_code == 403


def test_admin_nav_link(client):
    admin_client = _admin_client(client)
    factories.make_lot(slots={"Standard": 1})

    content = admin_client.get(reverse("lots:map")).content.decode()
    assert 'href="/lots/map/"' in content
    assert ">Lot map<" in content
