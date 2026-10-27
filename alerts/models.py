from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class NotificationLog(TimeStampedModel):
    """
    The dedupe table, and the single most important object in the alerts
    module.

    Without it, a compliance sitting at 85 days trips the 90-day rung
    every morning for three months, everyone mutes the system, and then
    the alert that actually mattered is ignored too. A muted system is
    worse than no system.

    It is also the audit asset: when a licence lapses and someone asks
    how, this table shows who was warned, when, and on what channel.
    """

    class Channel(models.TextChoices):
        INAPP = "inapp", "In-app"
        EMAIL = "email", "Email"
        SMS = "sms", "SMS"

    class Kind(models.TextChoices):
        THRESHOLD = "threshold", "Expiry threshold"
        DIGEST = "digest", "Weekly digest"
        EVENT = "event", "Event"

    period = models.ForeignKey(
        "compliance.CompliancePeriod",
        on_delete=models.CASCADE, related_name="notifications",
        null=True, blank=True,
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="notifications",
    )

    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.THRESHOLD)
    channel = models.CharField(max_length=8, choices=Channel.choices)
    threshold_days = models.IntegerField(
        null=True, blank=True,
        help_text="Which rung fired: 365, 180, 90, 30, 7, 0. Null for digests.",
    )
    dedupe_date = models.DateField(
        null=True, blank=True,
        help_text="Set only for repeating rungs (7, 0) so they may fire once "
                  "per day. Null for one-shot rungs, which fire once ever.",
    )

    subject = models.CharField(max_length=200, blank=True)
    body = models.TextField(blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["period", "recipient", "channel", "threshold_days", "dedupe_date"],
                name="one_alert_per_rung_per_channel",
            )
        ]
        indexes = [
            models.Index(fields=["recipient", "read_at"]),
            models.Index(fields=["period", "threshold_days"]),
        ]

    def __str__(self):
        return f"{self.get_channel_display()} to {self.recipient} · {self.subject}"
