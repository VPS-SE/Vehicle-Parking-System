"""Give the forecast trainer's read-only role only the columns it needs (SAD 3.6).

The role itself is created outside Django (docker/postgres/init/02-forecast-role.sh), so
this does nothing where it does not exist, such as test databases.
"""

from django.db import migrations

GRANT = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'forecast_ro') THEN
        GRANT SELECT (id, is_archived) ON lots_lot TO forecast_ro;
        GRANT SELECT (id, lot_id, slot_type) ON lots_slot TO forecast_ro;
        GRANT SELECT (id, slot_id, status, entry_time, exit_time)
            ON reservations_reservation TO forecast_ro;
    END IF;
END $$;
"""
REVOKE = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'forecast_ro') THEN
        REVOKE ALL ON lots_lot, lots_slot, reservations_reservation FROM forecast_ro;
    END IF;
END $$;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("lots", "0003_slot_distance_rank_positive"),
        ("reservations", "0001_initial"),
    ]

    operations = [migrations.RunSQL(GRANT, REVOKE)]
