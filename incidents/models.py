"""
Incident reports -- a log of things that go wrong at a station: fires, spills,
theft, accidents, security or equipment problems. Pure record-keeping with a
self-selected severity label and an open/closed status. No score is computed.
"""

from django.conf import settings
from django.db import models

from accounts.managers import ScopedQuerySet
from core.models import TimeStampedModel


class IncidentQuerySet(ScopedQuerySet):
    def for_user(self, user):
        if user is None or not user.is_authenticated:
            return self.none()
        if user.sees_all_stations:
            return self
        station_ids = user.accessible_station_ids()
        if station_ids is None:
            return self
        if not station_ids:
            return self.none()
        return self.filter(station_id__in=station_ids)


class Incident(TimeStampedModel):
    class Category(models.TextChoices):
        FIRE = "fire", "Fire"
        SPILL = "spill", "Spill / leak"
        THEFT = "theft", "Theft"
        ACCIDENT = "accident", "Accident / injury"
        SECURITY = "security", "Security"
        EQUIPMENT = "equipment", "Equipment failure"
        OTHER = "other", "Other"

    class Severity(models.TextChoices):
        MINOR = "minor", "Minor"
        MODERATE = "moderate", "Moderate"
        MAJOR = "major", "Major"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        REVIEW = "review", "Under review"
        CLOSED = "closed", "Closed"

    station = models.ForeignKey(
        "stations.Station", on_delete=models.CASCADE, related_name="incidents",
    )
    occurred_on = models.DateField()
    occurred_time = models.TimeField(null=True, blank=True)
    category = models.CharField(max_length=12, choices=Category.choices, default=Category.OTHER)
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.MINOR)
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    reported_by = models.CharField(max_length=120, blank=True, help_text="Who reported it at the station.")
    action_taken = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    logged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="incidents_logged",
    )

    objects = IncidentQuerySet.as_manager()

    class Meta:
        ordering = ["-occurred_on", "-created_at"]

    def __str__(self):
        return f"{self.title} — {self.station}"
