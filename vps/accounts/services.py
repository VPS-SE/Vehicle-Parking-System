"""Account registration rules shared by forms and other callers."""

import re
from datetime import timedelta

from django.contrib.auth import SESSION_KEY
from django.contrib.auth.password_validation import validate_password
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from vps.accounts.models import User
from vps.accounts.roles import Function, can
from vps.audit.services import log_action

DUPLICATE_EMAIL = "An account with this e-mail already exists"
EMAIL_CONSTRAINTS = ("accounts_user_email_key", "accounts_user_email_lower_uniq")

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)
FAILURE_WINDOW = timedelta(minutes=15)
IP_RATE_LIMIT_MAX_ATTEMPTS = 10
IP_RATE_LIMIT_WINDOW_SECONDS = 60


def register_driver(*, full_name, email, mobile, password):
    full_name = full_name.strip()
    email = User.objects.normalize_email(email.strip())
    user = User(full_name=full_name, email=email, mobile=mobile, role=User.Role.DRIVER)
    errors = {}
    if not 2 <= len(full_name) <= 100:
        errors["full_name"] = ["Enter a full name of 2 to 100 characters."]
    if not re.fullmatch(r"[6-9][0-9]{9}", mobile):
        errors["mobile"] = ["Enter 10 digits, starting with 6, 7, 8 or 9."]
    try:
        user.full_clean(exclude=["password"], validate_unique=False, validate_constraints=False)
    except ValidationError as error:
        errors.update(error.message_dict)
    if User.objects.filter(email__iexact=email).exists():
        errors["email"] = [DUPLICATE_EMAIL]
    try:
        validate_password(password, user)
    except ValidationError as error:
        errors["password"] = error.messages
    if errors:
        raise ValidationError(errors)
    try:
        with transaction.atomic():
            return User.objects.create_user(
                email,
                password,
                full_name=full_name,
                mobile=mobile,
                role=User.Role.DRIVER,
            )
    except IntegrityError as error:
        constraint = getattr(getattr(error.__cause__, "diag", None), "constraint_name", None)
        if constraint in EMAIL_CONSTRAINTS:
            raise ValidationError({"email": DUPLICATE_EMAIL}) from error
        raise

def create_staff(*, full_name, email, mobile, password, role, actor=None):
    full_name = full_name.strip()
    email = User.objects.normalize_email(email.strip())

    if role not in (User.Role.ATTENDANT, User.Role.ADMIN):
        raise ValidationError({
            "role": "Only staff roles can be created here."
        })

    user = User(
        full_name=full_name,
        email=email,
        mobile=mobile,
        role=role,
    )

    errors = {}

    try:
        user.full_clean(
            exclude=["password"],
            validate_unique=False,
            validate_constraints=False,
        )
    except ValidationError as error:
        errors.update(error.message_dict)

    if User.objects.filter(email__iexact=email).exists():
        errors["email"] = [DUPLICATE_EMAIL]

    try:
        validate_password(password, user)
    except ValidationError as error:
        errors["password"] = error.messages

    if errors:
        raise ValidationError(errors)

    try:
        with transaction.atomic():
            staff = User.objects.create_user(
                email=email,
                password=password,
                full_name=full_name,
                mobile=mobile,
                role=role,
            )
            log_action(
                actor=actor,
                action="staff.created",
                target=f"user:{staff.email}",
                after={"role": staff.role, "full_name": staff.full_name},
            )
            return staff
    except IntegrityError as error:
        constraint = getattr(getattr(error.__cause__, "diag", None), "constraint_name", None)
        if constraint in EMAIL_CONSTRAINTS:
            raise ValidationError({"email": DUPLICATE_EMAIL}) from error
        raise


def set_accessible_permit(admin, driver, has_permit):
    """FR-AUTH-06: a Lot Administrator records a Driver's permit, audited when it changes."""
    if not can(admin, Function.MANAGE_STAFF):
        raise ValidationError({"__all__": "Only Lot Administrators may change permits."})
    if driver.role != User.Role.DRIVER:
        raise ValidationError({"__all__": "Only Drivers can hold an accessible-parking permit."})
    if driver.accessible_permit == has_permit:
        return driver
    with transaction.atomic():
        log_action(
            actor=admin,
            action="driver.permit_changed",
            target=f"user:{driver.pk}",
            before={"accessible_permit": driver.accessible_permit},
            after={"accessible_permit": has_permit},
        )
        driver.accessible_permit = has_permit
        driver.save(update_fields=["accessible_permit"])
    return driver


def _invalidate_user_sessions(user):
    """Delete all unexpired database sessions belonging to this user."""
    sessions = Session.objects.filter(expire_date__gt=timezone.now())

    session_ids = [
        session.session_key
        for session in sessions.iterator()
        if session.get_decoded().get(SESSION_KEY) == str(user.pk)
    ]

    if session_ids:
        Session.objects.filter(session_key__in=session_ids).delete()


def deactivate_staff(admin, staff):
    """FR-AUTH-05: deactivate a staff account and invalidate its sessions."""
    if not can(admin, Function.MANAGE_STAFF):
        raise ValidationError(
            {"__all__": "Only Lot Administrators may manage staff accounts."}
        )

    if staff.role not in (User.Role.ATTENDANT, User.Role.ADMIN):
        raise ValidationError({"__all__": "Only staff accounts can be deactivated."})
    if staff.pk == admin.pk:
        # Otherwise the last administrator could lock everyone out of staff management.
        raise ValidationError({"__all__": "You cannot deactivate your own account."})

    with transaction.atomic():
        staff = User.objects.select_for_update().get(pk=staff.pk)

        if not staff.is_active:
            return staff

        staff.is_active = False
        staff.save(update_fields=["is_active"])

        _invalidate_user_sessions(staff)

        log_action(
            actor=admin,
            action="staff.deactivated",
            target=f"user:{staff.pk}",
            before={"is_active": True},
            after={"is_active": False},
        )

    return staff


def reactivate_staff(admin, staff):
    """FR-AUTH-05: reactivate a previously deactivated staff account."""
    if not can(admin, Function.MANAGE_STAFF):
        raise ValidationError(
            {"__all__": "Only Lot Administrators may manage staff accounts."}
        )

    if staff.role not in (User.Role.ATTENDANT, User.Role.ADMIN):
        raise ValidationError({"__all__": "Only staff accounts can be reactivated."})

    with transaction.atomic():
        staff = User.objects.select_for_update().get(pk=staff.pk)

        if staff.is_active:
            return staff

        staff.is_active = True
        staff.save(update_fields=["is_active"])

        log_action(
            actor=admin,
            action="staff.reactivated",
            target=f"user:{staff.pk}",
            before={"is_active": False},
            after={"is_active": True},
        )

    return staff


def get_client_ip(request) -> str:
    """The peer address. X-Forwarded-For is client-controlled, so it is not trusted here."""
    return request.META.get("REMOTE_ADDR", "")


def is_ip_rate_limited(ip_address: str) -> bool:
    """SEC-02: limit sign-in attempts to 10 per minute per IP address."""
    if not ip_address:
        return False
    key = f"signin_attempts:{ip_address}"
    now = timezone.now().timestamp()
    attempts = cache.get(key) or []
    valid_attempts = [t for t in attempts if now - t < IP_RATE_LIMIT_WINDOW_SECONDS]
    if len(valid_attempts) >= IP_RATE_LIMIT_MAX_ATTEMPTS:
        return True
    valid_attempts.append(now)
    cache.set(key, valid_attempts, timeout=IP_RATE_LIMIT_WINDOW_SECONDS)
    return False


def is_locked(user: User | None) -> bool:
    """SEC-02: return True if the account is currently locked."""
    if not user or not user.locked_until:
        return False
    return user.locked_until > timezone.now()


def record_failed_sign_in(
    *,
    email: str,
    ip_address: str = "",
    user: User | None = None,
) -> User | None:
    """SEC-02: record failed sign-in attempt, lock account if 5th failure in 15m, and audit."""
    if user is None and email:
        user = User.objects.filter(email__iexact=email).first()

    now = timezone.now()

    if user is not None:
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=user.pk)
            if (
                (user.locked_until is not None and user.locked_until <= now)
                or (
                    user.first_failed_at is not None
                    and (now - user.first_failed_at > FAILURE_WINDOW)
                )
                or (user.failed_attempts == 0)
            ):
                user.failed_attempts = 1
                user.first_failed_at = now
                user.locked_until = None
            else:
                user.failed_attempts += 1
                if not user.first_failed_at:
                    user.first_failed_at = now

            is_locking = False
            if user.failed_attempts >= MAX_FAILED_ATTEMPTS:
                user.locked_until = now + LOCKOUT_DURATION
                is_locking = True

            user.save(update_fields=["failed_attempts", "first_failed_at", "locked_until"])

        log_action(
            actor=None,
            action="auth.failed",
            target=f"user:{user.pk}",
            after={"email": user.email, "ip": ip_address},
        )
        if is_locking:
            log_action(
                actor=None,
                action="auth.locked",
                target=f"user:{user.pk}",
                after={
                    "email": user.email,
                    "ip": ip_address,
                    "locked_until": user.locked_until.isoformat(),
                },
            )
        return user

    # Unknown e-mail - record auth.failed without revealing whether account exists
    log_action(
        actor=None,
        action="auth.failed",
        target=f"email:{email}",
        after={"email": email, "ip": ip_address},
    )
    return None


def reset_failed_sign_in(user: User) -> None:
    """SEC-02: reset failed attempt counter and lockout on successful sign-in."""
    if (
        user.failed_attempts != 0
        or user.first_failed_at is not None
        or user.locked_until is not None
    ):
        user.failed_attempts = 0
        user.first_failed_at = None
        user.locked_until = None
        user.save(update_fields=["failed_attempts", "first_failed_at", "locked_until"])
