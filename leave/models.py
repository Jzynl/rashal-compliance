"""
Leave -- registers of annual and sick leave.

Entitlements (how many days a year each leave type grants) are NOT hardcoded.
The company's documents showed figures, but those are treated as data to be
confirmed, not approved policy, so each LeaveType's yearly entitlement is a
field you fill in. Until it is set, the module records leave taken and totals
it, but shows no "remaining" figure (there is nothing to subtract from).
"""

from decimal import Decimal

from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class LeaveType(TimeStampedModel):
    name = models.CharField(max_length=60)
    is_paid = models.BooleanField(default=True)
    annual_entitlement_days = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Days granted per year. Leave blank until the policy figure is confirmed.",
    )
    is_active = models.BooleanField(default=True)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class LeaveBalance(TimeStampedModel):
    """
    One employee's balance for one leave type in one year -- matching the
    company's leave sheets: an allowance, what has been taken (annual leave is
    taken in up to two instalments), and what remains. Remaining is allowed
    minus taken and may go negative, exactly as the sick-days sheet shows.
    """

    class Status(models.TextChoices):
        NONE = "", "—"
        CONFIRMED = "confirmed", "Confirmed"
        PAID = "paid", "Paid"

    employee = models.ForeignKey(
        "foundation.Employee", on_delete=models.CASCADE, related_name="leave_balances",
    )
    leave_type = models.ForeignKey(
        LeaveType, on_delete=models.PROTECT, related_name="balances",
    )
    year = models.PositiveSmallIntegerField()
    allowed = models.PositiveSmallIntegerField(
        default=0, help_text="Days granted this year (from the leave type, editable).",
    )
    taken_first = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal("0"))
    taken_second = models.DecimalField(
        max_digits=5, decimal_places=1, default=Decimal("0"),
        help_text="Second instalment (annual leave). Leave 0 for sick leave.",
    )
    status = models.CharField(max_length=10, choices=Status.choices, blank=True, default="")
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = [("employee", "leave_type", "year")]
        ordering = ["employee__first_name", "employee__last_name"]

    def __str__(self):
        return f"{self.employee} — {self.leave_type} {self.year}"

    @property
    def taken_total(self):
        return (self.taken_first or Decimal("0")) + (self.taken_second or Decimal("0"))

    @property
    def remaining(self):
        return self.allowed - self.taken_total


class LeaveRecord(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    employee = models.ForeignKey(
        "foundation.Employee", on_delete=models.CASCADE, related_name="leave_records",
    )
    leave_type = models.ForeignKey(
        LeaveType, on_delete=models.PROTECT, related_name="records",
    )
    start_date = models.DateField()
    end_date = models.DateField()
    days = models.DecimalField(
        max_digits=5, decimal_places=1, default=Decimal("0"),
        help_text="Number of leave days this covers (you can enter half days).",
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.APPROVED)
    note = models.CharField(max_length=200, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="leave_recorded",
    )

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.employee} — {self.leave_type} ({self.start_date})"

    @property
    def suggested_days(self):
        """Inclusive calendar-day span, as a hint. Not auto-applied."""
        if self.start_date and self.end_date and self.end_date >= self.start_date:
            return (self.end_date - self.start_date).days + 1
        return None
