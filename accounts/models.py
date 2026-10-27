import re

from django.contrib.auth.models import AbstractUser
from django.db import models

from core import roles


def normalise_phone(raw, default_cc="255"):
    """
    Tanzanian numbers arrive in every shape: 0754123456, +255754123456,
    255 754 123 456, 754123456. Normalise on save so the send path never
    has to think about it.

    Returns E.164 without the plus, e.g. 255754123456.
    """
    if not raw:
        return ""
    digits = re.sub(r"\D", "", str(raw))
    if not digits:
        return ""
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith(default_cc):
        return digits
    if digits.startswith("0"):
        return default_cc + digits[1:]
    if len(digits) == 9:
        return default_cc + digits
    return digits


class User(AbstractUser):
    """
    A person. Stations are many-to-many, not a single FK, because a
    'regional manager' covers several stations and a station can have
    more than one manager.
    """

    phone = models.CharField(max_length=20, blank=True)
    phone_raw = models.CharField(
        max_length=40, blank=True,
        help_text="Exactly what was typed, kept in case normalisation is wrong.",
    )
    stations = models.ManyToManyField(
        "stations.Station", blank=True, related_name="managers",
    )
    receives_digest = models.BooleanField(
        default=True,
        help_text="Weekly Monday summary. Super admins always receive it.",
    )
    job_title = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ["first_name", "last_name", "username"]

    def save(self, *args, **kwargs):
        if self.phone:
            if self.phone != self.phone_raw:
                self.phone_raw = self.phone_raw or self.phone
            self.phone = normalise_phone(self.phone)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.get_full_name() or self.username

    # -- roles ------------------------------------------------------------

    @property
    def role_names(self):
        if not hasattr(self, "_role_names"):
            self._role_names = set(self.groups.values_list("name", flat=True))
        return self._role_names

    def has_role(self, name):
        return name in self.role_names

    def has_any_role(self, names):
        return bool(self.role_names & set(names))

    @property
    def primary_role(self):
        for role in roles.ALL_ROLES:
            if self.has_role(role):
                return role
        return None

    @property
    def role_label(self):
        return roles.ROLE_LABELS.get(self.primary_role, "No role")

    @property
    def sees_all_stations(self):
        return self.is_superuser or self.has_any_role(roles.GLOBAL_SCOPE_ROLES)

    @property
    def can_write(self):
        return self.is_superuser or self.has_any_role(roles.WRITE_ROLES)

    def accessible_station_ids(self):
        """The station ids this user may see. None means 'all'."""
        if self.sees_all_stations:
            return None
        return list(self.stations.values_list("id", flat=True))

    @property
    def digest_recipient(self):
        return self.receives_digest or self.has_role(roles.SUPER_ADMIN)
