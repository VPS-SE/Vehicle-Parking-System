from django.core.management.base import BaseCommand

from vps.factories import DEMO_LOT_NAME, seed_demo


class Command(BaseCommand):
    help = "Create the demo data set: one 500-slot lot with 30 days of reservations."

    def add_arguments(self, parser):
        parser.add_argument("--seed", type=int, default=2026, help="random seed (logged)")

    def handle(self, *args, seed, **options):
        summary = seed_demo(seed=seed)
        if summary is None:
            self.stdout.write(f'Lot "{DEMO_LOT_NAME}" already exists; nothing was added.')
            return
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded seed={summary['seed']}: {summary['slots']} slots, "
                f"{summary['drivers']} drivers, {summary['reservations']} reservations over "
                f"{summary['days']} days, {summary['charges']} charges."
            )
        )
