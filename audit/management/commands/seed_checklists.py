from django.core.management.base import BaseCommand

from audit.seeding import seed_checklists


class Command(BaseCommand):
    help = "Load/refresh the audit checklist templates. Idempotent."

    def handle(self, *args, **options):
        created = seed_checklists()
        self.stdout.write(
            f"Checklists seeded. New: {created['templates']} templates, "
            f"{created['sections']} sections, {created['items']} items."
        )
