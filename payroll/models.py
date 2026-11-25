"""
Payroll -- disbursement first.

This module deliberately does NOT calculate salaries. It records what each
person is paid in a given month and produces the bank payment file (the NMB
upload) from those figures. No statutory rates, no deductions, nothing
invented. A calculation engine can be layered on top later, once the rates
are confirmed; until then this simply replaces the hand-made bank sheet.

A PayRun is one month's payment batch. Each PayLine is one person's payment
in that batch, with their name and account snapshotted so a finalised run
never changes if the employee's details are edited afterwards.
"""

from decimal import Decimal

from django.conf import settings
from django.db import models

from core.models import TimeStampedModel

MONTHS = [
    (1, "January"), (2, "February"), (3, "March"), (4, "April"),
    (5, "May"), (6, "June"), (7, "July"), (8, "August"),
    (9, "September"), (10, "October"), (11, "November"), (12, "December"),
]
_MONTH_ABBR = {
    1: "JAN", 2: "FEB", 3: "MAR", 4: "APR", 5: "MAY", 6: "JUN",
    7: "JUL", 8: "AUG", 9: "SEP", 10: "OCT", 11: "NOV", 12: "DEC",
}


class PayRun(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        FINAL = "final", "Finalised"

    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField(choices=MONTHS)

    # These map onto the NMB bank file columns. Defaults match the sample file.
    reference = models.CharField(
        max_length=40, blank=True,
        help_text="Ownreference column, e.g. OCT. Auto-filled from the month if left blank.",
    )
    narration = models.CharField(max_length=40, default="SALARY")
    payment_type = models.CharField(max_length=20, default="INTERNAL")
    destination = models.CharField(max_length=40, default="NMB")

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    note = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="pay_runs",
    )

    class Meta:
        ordering = ["-year", "-month", "-created_at"]

    def __str__(self):
        return f"{self.get_month_display()} {self.year}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = _MONTH_ABBR.get(self.month, "")
        super().save(*args, **kwargs)

    @property
    def is_final(self):
        return self.status == self.Status.FINAL

    @property
    def included_lines(self):
        return self.lines.filter(include=True)

    @property
    def headcount(self):
        return self.included_lines.count()

    @property
    def total_amount(self):
        total = self.included_lines.aggregate(t=models.Sum("amount"))["t"]
        return total or Decimal("0")


class PayLine(TimeStampedModel):
    pay_run = models.ForeignKey(PayRun, on_delete=models.CASCADE, related_name="lines")
    employee = models.ForeignKey(
        "foundation.Employee", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="pay_lines",
    )

    # Snapshots -- what actually goes on the bank file for this run.
    beneficiary_name = models.CharField(max_length=160)
    beneficiary_account = models.CharField(max_length=40, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    narration = models.CharField(
        max_length=40, blank=True,
        help_text="Leave blank to use the run's narration (SALARY).",
    )
    include = models.BooleanField(
        default=True, help_text="Untick to leave this person out of the bank file without deleting them.",
    )

    class Meta:
        ordering = ["beneficiary_name"]

    def __str__(self):
        return f"{self.beneficiary_name} — {self.amount}"

    @property
    def narration_value(self):
        return self.narration or self.pay_run.narration


# --------------------------------------------------------------------------
# Retrenchment (severance) payouts
# --------------------------------------------------------------------------
# These amounts are entered/imported already calculated. This module records
# and disburses them; it does NOT compute severance (no formula is assumed).
class RetrenchmentBatch(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        FINAL = "final", "Finalised"

    station = models.ForeignKey(
        "stations.Station", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="retrenchments",
    )
    year = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=120, default="Retrenchment benefits")
    description = models.CharField(
        max_length=120, default="Ret. Benefit",
        help_text="Goes in the Description column of the payout file.",
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    note = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="retrenchment_batches",
    )

    class Meta:
        ordering = ["-year", "-created_at"]

    def __str__(self):
        loc = self.station.name if self.station else "All"
        return f"{self.title} — {loc} {self.year}"

    @property
    def is_final(self):
        return self.status == self.Status.FINAL

    @property
    def included_payments(self):
        return self.payments.filter(include=True)

    @property
    def headcount(self):
        return self.included_payments.count()

    @property
    def total_amount(self):
        total = self.included_payments.aggregate(t=models.Sum("amount"))["t"]
        return total or Decimal("0")


class RetrenchmentPayment(TimeStampedModel):
    batch = models.ForeignKey(RetrenchmentBatch, on_delete=models.CASCADE, related_name="payments")
    employee = models.ForeignKey(
        "foundation.Employee", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="retrenchment_payments",
    )
    name = models.CharField(max_length=160)
    account_no = models.CharField(max_length=40, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    bank = models.CharField(max_length=40, blank=True)
    branch = models.CharField(max_length=40, blank=True)
    description = models.CharField(max_length=120, blank=True)
    include = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} — {self.amount}"

    @property
    def description_value(self):
        return self.description or self.batch.description
