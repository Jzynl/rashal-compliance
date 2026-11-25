"""
Audit -- station audits built around reusable checklists.

Mirrors the company's real audit document: a checklist is a set of Yes/No
questions grouped into sections. An audit runs against a checklist template
and records an answer + comment for each item. Items answered "No" are the
issues to act on. There is deliberately NO scoring and no pass/fail rule --
the source document has none, so neither does this.

Free-form findings remain available for anything outside the checklist.
"""

from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


# --------------------------------------------------------------------------
# Checklist templates (the reusable question sets)
# --------------------------------------------------------------------------
class ChecklistTemplate(TimeStampedModel):
    name = models.CharField(max_length=160)
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    @property
    def item_count(self):
        return ChecklistItem.objects.filter(section__template=self).count()


class ChecklistSection(TimeStampedModel):
    template = models.ForeignKey(
        ChecklistTemplate, on_delete=models.CASCADE, related_name="sections",
    )
    label = models.CharField(max_length=8, blank=True, help_text="e.g. A, B, C.")
    title = models.CharField(max_length=160)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.label} {self.title}".strip()


class ChecklistItem(TimeStampedModel):
    section = models.ForeignKey(
        ChecklistSection, on_delete=models.CASCADE, related_name="items",
    )
    text = models.TextField()
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.text[:70]


# --------------------------------------------------------------------------
# Audits
# --------------------------------------------------------------------------
class Audit(TimeStampedModel):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"

    station = models.ForeignKey(
        "stations.Station", on_delete=models.CASCADE, related_name="audits",
    )
    template = models.ForeignKey(
        ChecklistTemplate, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="audits", help_text="The checklist this audit uses. Optional.",
    )
    title = models.CharField(max_length=160, help_text="e.g. Internal audit, EWURA inspection.")
    audit_date = models.DateField(null=True, blank=True)
    auditor_name = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PLANNED)
    summary = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="audits_created",
    )

    class Meta:
        ordering = ["-audit_date", "-created_at"]

    def __str__(self):
        return f"{self.title} — {self.station}"

    # Free-form findings
    @property
    def open_findings_count(self):
        return self.findings.filter(status=AuditFinding.Status.OPEN).count()

    @property
    def total_findings_count(self):
        return self.findings.count()

    # Checklist roll-up (counts only -- never a score)
    @property
    def answered_count(self):
        return self.responses.exclude(answer=AuditResponse.Answer.BLANK).count()

    @property
    def no_count(self):
        return self.responses.filter(answer=AuditResponse.Answer.NO).count()


class AuditResponse(TimeStampedModel):
    class Answer(models.TextChoices):
        BLANK = "", "—"
        YES = "yes", "Yes"
        NO = "no", "No"
        NA = "na", "N/A"

    audit = models.ForeignKey(Audit, on_delete=models.CASCADE, related_name="responses")
    item = models.ForeignKey(ChecklistItem, on_delete=models.CASCADE, related_name="responses")
    answer = models.CharField(max_length=4, choices=Answer.choices, blank=True, default=Answer.BLANK)
    comment = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = [("audit", "item")]

    def __str__(self):
        return f"{self.item_id}: {self.answer or '—'}"


class AuditFinding(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        RESOLVED = "resolved", "Resolved"

    audit = models.ForeignKey(Audit, on_delete=models.CASCADE, related_name="findings")
    description = models.TextField()
    category = models.CharField(
        max_length=80, blank=True, help_text="Optional label, e.g. Safety, Housekeeping, Documentation.",
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    responsible = models.CharField(max_length=120, blank=True, help_text="Who is to act on it.")
    due_date = models.DateField(null=True, blank=True)
    resolution_note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["status", "due_date", "id"]

    def __str__(self):
        return self.description[:60]
