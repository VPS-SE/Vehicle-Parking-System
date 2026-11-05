"""TC-04: Validate vehicle registration number format.

Requirements: FR-VEH-02, FR-VEH-03
Preconditions: Signed in as a Driver with no vehicles.
Steps:
  1. Add vehicle "ka 01 ab 1234" (Car).
  2. Add vehicle "22BH1234AA" (Car).
  3. Add vehicle "KA01AB12" (Car).
  4. Add "KA01AB1234" again.
Expected result:
  First stored as KA01AB1234; second accepted; third rejected as invalid format;
  fourth rejected as duplicate.
"""

import pytest
from django.core.exceptions import ValidationError

from vps.accounts.models import User
from vps.vehicles import services
from vps.vehicles.models import Vehicle

pytestmark = pytest.mark.django_db


@pytest.fixture
def driver():
    return User.objects.create_user(
        email="driver@example.com",
        password="ValidPassword2026!",
        role=User.Role.DRIVER,
    )


def test_tc04_validate_vehicle_registration_number_format(client, driver):
    """TC-04: executes the exact 4-step sequence for vehicle registration validation."""
    client.force_login(driver)
    assert Vehicle.objects.filter(owner=driver).count() == 0

    # Step 1: Add vehicle "ka 01 ab 1234" (Car)
    resp1 = client.post(
        "/vehicles/",
        {
            "registration_no": "ka 01 ab 1234",
            "vehicle_type": "Car",
            "nickname": "Daily",
        },
        follow=True,
    )
    assert resp1.status_code == 200
    v1 = Vehicle.objects.get(registration_no="KA01AB1234")
    assert v1.owner == driver
    assert v1.vehicle_type == "Car"
    assert v1.is_active is True

    # Step 2: Add vehicle "22BH1234AA" (Car)
    resp2 = client.post(
        "/vehicles/",
        {
            "registration_no": "22BH1234AA",
            "vehicle_type": "Car",
            "nickname": "BH Car",
        },
        follow=True,
    )
    assert resp2.status_code == 200
    v2 = Vehicle.objects.get(registration_no="22BH1234AA")
    assert v2.owner == driver
    assert v2.vehicle_type == "Car"
    assert v2.is_active is True
    assert Vehicle.objects.filter(owner=driver).count() == 2

    # Step 3: Add vehicle "KA01AB12" (Car) -> rejected as invalid format
    resp3 = client.post(
        "/vehicles/",
        {
            "registration_no": "KA01AB12",
            "vehicle_type": "Car",
            "nickname": "Short",
        },
    )
    assert resp3.status_code == 200
    assert "registration_no" in resp3.context["form"].errors
    assert not Vehicle.objects.filter(registration_no="KA01AB12").exists()

    with pytest.raises(ValidationError) as exc_info:
        services.add_vehicle(driver, "KA01AB12", "Car")
    assert "registration_no" in exc_info.value.message_dict

    # Step 4: Add "KA01AB1234" again -> rejected as duplicate
    resp4 = client.post(
        "/vehicles/",
        {
            "registration_no": "KA01AB1234",
            "vehicle_type": "Car",
            "nickname": "Duplicate",
        },
    )
    assert resp4.status_code == 200
    assert "registration_no" in resp4.context["form"].errors
    assert Vehicle.objects.filter(owner=driver).count() == 2

    with pytest.raises(ValidationError) as exc_info_dup:
        services.add_vehicle(driver, "KA01AB1234", "Car")
    assert "registration_no" in exc_info_dup.value.message_dict
