"""Tests for finding F1: case-insensitive email comparison and storage.

Covers edge cases:
- duplicate refused with different case for drivers and for staff (service and views);
- the stored e-mail is lowercase (driver, staff, create_user, create_superuser);
- signing in with an upper-case version of the address works (form/view and authenticate);
- the DB constraint rejects a raw case-variant insert (IntegrityError).
"""

import pytest
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.urls import reverse
from django.utils import timezone

from vps.accounts import services as account_services
from vps.accounts.models import User

pytestmark = pytest.mark.django_db


def test_driver_duplicate_email_refused_with_different_case(client):
    """Registering a driver with case-variant email is rejected at service and view levels."""
    account_services.register_driver(
        full_name="Asha Rao",
        email="asha.rao@example.com",
        mobile="9876543210",
        password="ValidPassword2026!",
    )
    assert User.objects.filter(email="asha.rao@example.com").count() == 1

    # Service layer rejection with uppercase
    with pytest.raises(ValidationError) as exc:
        account_services.register_driver(
            full_name="Asha Rao",
            email="ASHA.RAO@EXAMPLE.COM",
            mobile="9876543211",
            password="ValidPassword2026!",
        )
    assert "email" in exc.value.message_dict
    assert exc.value.message_dict["email"] == [account_services.DUPLICATE_EMAIL]

    # Service layer rejection with mixed case
    with pytest.raises(ValidationError) as exc:
        account_services.register_driver(
            full_name="Asha Rao",
            email="Asha.Rao@Example.Com",
            mobile="9876543212",
            password="ValidPassword2026!",
        )
    assert "email" in exc.value.message_dict
    assert exc.value.message_dict["email"] == [account_services.DUPLICATE_EMAIL]

    # View layer registration rejection with uppercase
    response = client.post(
        "/accounts/register/",
        {
            "full_name": "Asha Rao",
            "email": "ASHA.RAO@EXAMPLE.COM",
            "mobile": "9876543213",
            "password": "ValidPassword2026!",
        },
    )
    assert response.status_code == 200
    assert "form" in response.context
    assert response.context["form"].errors["email"] == [account_services.DUPLICATE_EMAIL]
    assert User.objects.count() == 1


def test_staff_duplicate_email_refused_with_different_case(client):
    """Creating staff with case-variant email is rejected at service and view levels."""
    account_services.create_staff(
        full_name="Staff Attendant",
        email="staff.attendant@example.com",
        mobile="9876543210",
        password="ValidPassword2026!",
        role=User.Role.ATTENDANT,
    )
    assert User.objects.filter(email="staff.attendant@example.com").count() == 1

    # Attendant duplication via uppercase
    with pytest.raises(ValidationError) as exc:
        account_services.create_staff(
            full_name="Staff Attendant 2",
            email="STAFF.ATTENDANT@EXAMPLE.COM",
            mobile="9876543211",
            password="ValidPassword2026!",
            role=User.Role.ATTENDANT,
        )
    assert "email" in exc.value.message_dict
    assert exc.value.message_dict["email"] == [account_services.DUPLICATE_EMAIL]

    # Admin duplication via mixed case
    with pytest.raises(ValidationError) as exc:
        account_services.create_staff(
            full_name="Staff Admin",
            email="Staff.Attendant@Example.Com",
            mobile="9876543212",
            password="ValidPassword2026!",
            role=User.Role.ADMIN,
        )
    assert "email" in exc.value.message_dict
    assert exc.value.message_dict["email"] == [account_services.DUPLICATE_EMAIL]

    # Cross-role: cannot register driver when staff has case-variant email
    with pytest.raises(ValidationError) as exc:
        account_services.register_driver(
            full_name="Driver Person",
            email="STAFF.ATTENDANT@EXAMPLE.COM",
            mobile="9876543213",
            password="ValidPassword2026!",
        )
    assert "email" in exc.value.message_dict
    assert exc.value.message_dict["email"] == [account_services.DUPLICATE_EMAIL]

    # View layer: admin creating staff with duplicate case-variant
    admin = account_services.create_staff(
        full_name="Admin Boss",
        email="admin.boss@example.com",
        mobile="9876543214",
        password="ValidPassword2026!",
        role=User.Role.ADMIN,
    )
    client.force_login(admin)
    response = client.post(
        reverse("accounts:create_staff"),
        {
            "full_name": "Another Staff",
            "email": "STAFF.ATTENDANT@EXAMPLE.COM",
            "mobile": "9876543215",
            "password": "ValidPassword2026!",
            "role": User.Role.ATTENDANT,
        },
    )
    assert response.status_code == 200
    assert "form" in response.context
    assert response.context["form"].errors["email"] == [account_services.DUPLICATE_EMAIL]


def test_stored_email_is_lowercase():
    """All creation paths persist lowercase email strings."""
    # 1. register_driver
    driver = account_services.register_driver(
        full_name="Driver One",
        email="DRIVER.ONE@EXAMPLE.COM",
        mobile="9876543210",
        password="ValidPassword2026!",
    )
    assert driver.email == "driver.one@example.com"
    assert User.objects.get(pk=driver.pk).email == "driver.one@example.com"

    # 2. create_staff
    staff = account_services.create_staff(
        full_name="Staff One",
        email="STAFF.ONE@EXAMPLE.COM",
        mobile="9876543211",
        password="ValidPassword2026!",
        role=User.Role.ATTENDANT,
    )
    assert staff.email == "staff.one@example.com"
    assert User.objects.get(pk=staff.pk).email == "staff.one@example.com"

    # 3. User.objects.create_user
    user = User.objects.create_user(
        email="CREATE.USER@EXAMPLE.COM",
        password="ValidPassword2026!",
        full_name="Create User",
        mobile="9876543212",
    )
    assert user.email == "create.user@example.com"
    assert User.objects.get(pk=user.pk).email == "create.user@example.com"

    # 4. User.objects.create_superuser
    admin = User.objects.create_superuser(
        email="SUPER.USER@EXAMPLE.COM",
        password="ValidPassword2026!",
    )
    assert admin.email == "super.user@example.com"
    assert User.objects.get(pk=admin.pk).email == "super.user@example.com"


def test_sign_in_with_uppercase_email(client):
    """User can authenticate and log in regardless of email casing typed."""
    password = "ValidPassword2026!"
    user = account_services.register_driver(
        full_name="Login Test Driver",
        email="driver.signin@example.com",
        mobile="9876543210",
        password=password,
    )
    assert user.email == "driver.signin@example.com"

    # Direct authenticate call with all uppercase
    auth_user = authenticate(email="DRIVER.SIGNIN@EXAMPLE.COM", password=password)
    assert auth_user is not None
    assert auth_user.pk == user.pk

    # Direct authenticate call with mixed case
    auth_user_mixed = authenticate(email="Driver.SignIn@Example.Com", password=password)
    assert auth_user_mixed is not None
    assert auth_user_mixed.pk == user.pk

    # Sign in via HTTP view with uppercase email
    response = client.post(
        "/accounts/login/",
        {"email": "DRIVER.SIGNIN@EXAMPLE.COM", "password": password},
    )
    assert response.status_code == 302
    assert client.session["_auth_user_id"] == str(user.pk)

    # Client can access home dashboard
    home_resp = client.get("/")
    assert home_resp.status_code == 302
    assert home_resp.url == "/vehicles/"


def test_db_constraint_rejects_raw_case_variant_insert():
    """Database UniqueConstraint on Lower('email') rejects raw case-variant inserts."""
    user = account_services.register_driver(
        full_name="Existing Driver",
        email="db.constraint@example.com",
        mobile="9876543210",
        password="ValidPassword2026!",
    )
    assert user.email == "db.constraint@example.com"

    # Direct raw SQL insert with uppercase email variant must violate the constraint
    with (
        pytest.raises(IntegrityError) as exc_info,
        transaction.atomic(),
        connection.cursor() as cursor,
    ):
        cursor.execute(
            """
            INSERT INTO accounts_user (
                password, is_superuser, first_name, last_name, email, full_name, mobile,
                role, accessible_permit, failed_attempts, is_staff, is_active,
                date_joined
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s
            )
            """,
            [
                "pbkdf2_sha256$test$hash",
                False,
                "",
                "",
                "DB.CONSTRAINT@EXAMPLE.COM",
                "Duplicate Raw User",
                "9876543211",
                "Driver",
                False,
                0,
                False,
                True,
                timezone.now(),
            ],
        )
    assert "accounts_user_email_lower_uniq" in str(exc_info.value)

    # Bulk create bypassing model save/clean also triggers IntegrityError
    with pytest.raises(IntegrityError) as exc_info, transaction.atomic():
        User.objects.bulk_create(
            [
                User(
                    email="Db.Constraint@Example.Com",
                    password="pbkdf2_sha256$test$hash",
                    full_name="Duplicate Bulk User",
                    mobile="9876543212",
                    role=User.Role.DRIVER,
                )
            ]
        )
    assert "accounts_user_email_lower_uniq" in str(exc_info.value)
