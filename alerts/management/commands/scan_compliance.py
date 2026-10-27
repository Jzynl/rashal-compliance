"""
The daily scan. Wire to cron at 06:00 EAT:

    0 6 * * * cd /srv/rashal && python manage.py scan_compliance

Django has no scheduler. For a once-a-day walk across ~196 rows, cron is
genuinely the right answer -- do not reach for Celery.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from alerts.services import scan
from compliance.services import expire_lapsed_periods


class Command(BaseCommand):
    help = "Expire lapsed periods, then send any threshold alerts that are due."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would be sent without sending or logging.",
        )
        parser.add_argument(
            "--date", type=str, default=None,
            help="Pretend today is YYYY-MM-DD. For testing.",
        )

    def handle(self, *args, **options):
        today = None
        if options["date"]:
            today = timezone.datetime.strptime(options["date"], "%Y-%m-%d").date()

        expired = expire_lapsed_periods(today=today)
        self.stdout.write(f"Marked expired: {expired}")

        result = scan(today=today, dry_run=options["dry_run"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Scanned {result['considered']} period(s) for {result['date']}; "
                f"{'would send' if options['dry_run'] else 'sent'} {result['sent']} message(s)."
            )
        )
