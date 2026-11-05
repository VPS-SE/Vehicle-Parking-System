"""Create the system-test accounts and 200 signed-in load sessions.

Run against the system-test database (sessions are made directly, so the load tests do not
hit the 10-per-minute sign-in limit):

    python manage.py shell -c "import sys; sys.argv = ['x', 'load-sessions.json']; \
exec(open('tests/system/make_load_accounts.py').read())"

Sessions expire after 30 minutes without use (SEC-08), so run this shortly before the load
tests. Re-running it resets the passwords, which also ends the old sessions.
"""

import json
import sys
from pathlib import Path

from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
from django.contrib.sessions.backends.db import SessionStore

from vps.accounts.models import User
from vps.vehicles.models import Vehicle

PASSWORD = "SysTest!2026pass"
BACKEND = "django.contrib.auth.backends.ModelBackend"


def account(email, role, mobile):
    user, _ = User.objects.get_or_create(
        email=email, defaults={"role": role, "mobile": mobile, "full_name": email.split("@")[0]}
    )
    user.set_password(PASSWORD)
    user.save()
    return user


def signed_in_session(user):
    session = SessionStore()
    session[SESSION_KEY] = str(user.pk)
    session[BACKEND_SESSION_KEY] = BACKEND
    session[HASH_SESSION_KEY] = user.get_session_auth_hash()
    session.create()
    return session.session_key


account("sys.admin@example.com", User.Role.ADMIN, "9800000001")
account("sys.gate@example.com", User.Role.ATTENDANT, "9800000002")
account("sys.driver@example.com", User.Role.DRIVER, "9800000003")

drivers, attendants = [], []
for i in range(1, 201):
    user = account(f"load.driver{i:03d}@example.com", User.Role.DRIVER, f"97{i:08d}")
    vehicle, _ = Vehicle.objects.get_or_create(
        owner=user, registration_no=f"KA09LD{i:04d}", defaults={"vehicle_type": "Car"}
    )
    drivers.append(
        {
            "email": user.email,
            "vehicle": vehicle.registration_no,
            "sessionid": signed_in_session(user),
        }
    )
for i in range(1, 11):
    user = account(f"load.gate{i:02d}@example.com", User.Role.ATTENDANT, f"96{i:08d}")
    attendants.append({"email": user.email, "sessionid": signed_in_session(user)})

Path(sys.argv[1]).write_text(
    json.dumps({"password": PASSWORD, "drivers": drivers, "attendants": attendants}, indent=1)
)
print(len(drivers), "drivers,", len(attendants), "attendants ->", sys.argv[1])
