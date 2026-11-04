"""TC-02: Reject duplicate e-mail at registration.

Requirements: FR-AUTH-01
Preconditions: An account exists for asha@example.com.
Steps:
  1. Register again with e-mail asha@example.com and otherwise valid data.
Expected result:
  Registration refused with "An account with this e-mail already exists";
  no new account created.
"""

import pytest
from django.core.exceptions import ValidationError

from vps.accounts import services
from vps.accounts.models import User

pytestmark = pytest.mark.django_db


def test_tc02_reject_duplicate_email_at_registration(client):
    """TC-02: duplicate email is rejected with standard error message."""
    initial_user = services.register_driver(
        full_name="Asha Rao",
        email="asha@example.com",
        mobile="9876543210",
        password="ValidPassword2026!",
    )
    assert User.objects.count() == 1
    assert initial_user.email == "asha@example.com"

    response = client.post(
        "/accounts/register/",
        {
            "full_name": "Asha Rao",
            "email": "asha@example.com",
            "mobile": "9876543210",
            "password": "ValidPassword2026!",
        },
    )

    assert response.status_code == 200
    assert "form" in response.context
    assert response.context["form"].errors["email"] == [
        "An account with this e-mail already exists"
    ]
    assert User.objects.count() == 1

    with pytest.raises(ValidationError) as exc:
        services.register_driver(
            full_name="Asha Rao",
            email="asha@example.com",
            mobile="9876543210",
            password="ValidPassword2026!",
        )
    assert exc.value.message_dict["email"] == ["An account with this e-mail already exists"]
    assert User.objects.count() == 1
