"""TC-39: Password storage and data masking.

Requirements: SEC-01, SEC-09
Preconditions: Driver registered with password Park2026! and mobile 9876543210.
Steps:
  1. Read the user row in the database.
  2. Register with password "password".
Expected result:
  Stored value starts with pbkdf2_sha256$; the weak password is refused by validation.
"""

import pytest
from django.core.exceptions import ValidationError

from vps.accounts import services
from vps.accounts.models import User

pytestmark = pytest.mark.django_db


def test_tc39_password_storage_and_weak_password_rejection(client):
    """TC-39 steps 1-2: passwords use PBKDF2 hashing and weak passwords are rejected."""
    # Step 1: Register driver and verify hash format in database
    driver = services.register_driver(
        full_name="Asha Rao",
        email="asha@example.com",
        mobile="9876543210",
        password="Park2026!Strong",
    )
    db_user = User.objects.get(pk=driver.pk)
    # Stored password must use PBKDF2 with SHA-256
    assert db_user.password.startswith("pbkdf2_sha256$")

    # Step 2: Attempt registration with common/weak password "password"
    with pytest.raises(ValidationError) as exc_info:
        services.register_driver(
            full_name="Weak Password User",
            email="weak@example.com",
            mobile="9876543211",
            password="password",
        )
    assert "password" in exc_info.value.message_dict

    # Also test via registration view
    response = client.post(
        "/accounts/register/",
        {
            "full_name": "Weak User",
            "email": "weak2@example.com",
            "mobile": "9876543212",
            "password": "password",
        },
    )
    assert response.status_code == 200
    assert "password" in response.context["form"].errors
    assert not User.objects.filter(email="weak2@example.com").exists()
