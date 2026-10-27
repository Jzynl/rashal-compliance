"""Create the four groups. Idempotent; safe to run on every deploy."""

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from core import roles


class Command(BaseCommand):
    help = "Create the role groups."

    def handle(self, *args, **options):
        for name in roles.ALL_ROLES:
            group, created = Group.objects.get_or_create(name=name)
            verb = "Created" if created else "Exists"
            self.stdout.write(f"{verb}: {roles.ROLE_LABELS[name]} ({name})")
