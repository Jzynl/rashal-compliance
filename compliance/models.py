"""
The compliance domain.

Four models, deliberately layered:

    ComplianceType       "EWURA exists"                          ~14 rows
    StationCompliance    "Kariakoo must hold EWURA"    permanent ~196 rows
    CompliancePeriod     "Kariakoo's EWURA, Mar26-Mar27"         grows forever
    ComplianceDocument   the certificate / the receipt           never deleted

The split between StationCompliance and CompliancePeriod is what gives us
document history for free: a renewal creates a new period, it does not
overwrite the old one.
"""

from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from dateutil.relativedelta import relativedelta

from accounts.managers import ScopedQuerySet
from core import bands
from core.models import TimeStampedModel


def default_thresholds():
    return [365, 180, 90, 30, 7, 0]


# ---------------------------------------------------------------------------
# ComplianceType
# ---------------------------------------------------------------------------

class ComplianceTypeQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)


class ComplianceType(TimeStampedModel):
    """
    A category of obligation: EWURA, NEMC, Fire, OSHA, TRA...
    Admin-created. Never a hardcoded enum.
    """

    name = models.CharField(max_length=80, unique=True)
    short_code = models.CharField(max_length=16, unique=True)
    issuing_authority = models.CharField(max_length=160)
    description = models.TextField(blank=True)

    default_validity_months = models.PositiveSmallIntegerField(
        default=12,
        help_text="Pre-fills the expiry date on the renewal form. Always overridable.",
    )
    requires_payment_receipt = models.BooleanField(default=True)
    is_perpetual = models.BooleanField(
        default=False,
        help_text="True for obligations that never expire, e.g. a TRA TIN. "
                  "Perpetual types never alert and never show red.",
    )

    alert_thresholds = models.JSONField(
        default=default_thresholds,
        help_text="Days-before-expiry rungs that fire an alert, e.g. "
                  "[365, 180, 90, 30, 7, 0]. Per type, because Fire needs "
                  "30 days notice and EWURA needs six months.",
    )

    sort_order = models.PositiveSmallIntegerField(default=100)
    is_active = models.BooleanField(default=True)

    objects = ComplianceTypeQuerySet.as_manager()

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.short_code

    def get_absolute_url(self):
        return reverse("compliance:type_detail", args=[self.pk])

    def clean(self):
        if not isinstance(self.alert_thresholds, list):
            raise ValidationError({"alert_thresholds": "Must be a list of integers."})
        for value in self.alert_thresholds:
            if not isinstance(value, int) or value < 0:
                raise ValidationError(
                    {"alert_thresholds": "Every threshold must be a positive integer."}
                )

    @property
    def sorted_thresholds(self):
        return sorted(self.alert_thresholds, reverse=True)


# ---------------------------------------------------------------------------
# StationCompliance
# ---------------------------------------------------------------------------

class StationComplianceQuerySet(ScopedQuerySet):
    def _scope_filter(self, station_ids):
        return self.filter(station_id__in=station_ids)

    def live(self):
        return self.filter(station__is_active=True, compliance_type__is_active=True)

    def with_related(self):
        return self.select_related("station", "compliance_type", "current_period")


class StationCompliance(TimeStampedModel):
    """
    The obligation itself: "this station must hold this compliance."
    Permanent. Never expires. Points at whichever period is current.
    """

    station = models.ForeignKey(
        "stations.Station", on_delete=models.CASCADE, related_name="compliances",
    )
    compliance_type = models.ForeignKey(
        ComplianceType, on_delete=models.CASCADE, related_name="station_compliances",
    )
    label = models.CharField(
        max_length=80, blank=True,
        help_text="Only needed when a station holds more than one licence of "
                  "the same type, e.g. one EWURA per fuel grade.",
    )
    current_period = models.OneToOneField(
        "CompliancePeriod",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="+",
    )
    notes = models.TextField(blank=True)

    objects = StationComplianceQuerySet.as_manager()

    class Meta:
        ordering = ["station__name", "compliance_type__sort_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["station", "compliance_type", "label"],
                name="unique_station_compliance",
            )
        ]
        indexes = [
            models.Index(fields=["station", "compliance_type"]),
        ]
        verbose_name_plural = "station compliances"

    def __str__(self):
        base = f"{self.station.name} · {self.compliance_type.short_code}"
        return f"{base} ({self.label})" if self.label else base

    def get_absolute_url(self):
        return reverse("compliance:obligation_detail", args=[self.pk])

    # -- state ------------------------------------------------------------

    @property
    def latest_period(self):
        # nulls_first is load-bearing: a period still in processing has no
        # start_date yet, and it IS the latest. Plain "-start_date" sorts
        # those NULLs to the far end and silently loses the renewal.
        return self.periods.order_by(
            models.F("start_date").desc(nulls_first=True), "-created_at"
        ).first()

    @property
    def band(self):
        """
        Urgency for this obligation. Always via core.bands -- never
        recomputed inline.

        Note what this does NOT do: an in-flight renewal does not soften
        the band. If the old licence has lapsed, the obligation stays
        EXPIRED even while a renewal is processing, because the station
        is operating unlicensed either way. Processing is surfaced
        separately (see is_in_processing / lapsed_period) so the UI can
        show both truths at once. Collapsing them is how a manager sees
        "processing" and relaxes.
        """
        period = self.current_period
        if period is None:
            latest = self.latest_period
            if latest and latest.status == CompliancePeriod.Status.PROCESSING:
                return bands.PROCESSING
            return bands.UNKNOWN
        return period.band

    @property
    def days_left(self):
        if self.current_period is None:
            return None
        return self.current_period.days_left

    @property
    def is_in_processing(self):
        latest = self.latest_period
        return latest is not None and latest.status == CompliancePeriod.Status.PROCESSING

    @property
    def lapsed_period(self):
        """
        The expired period sitting behind an in-flight renewal.

        This is the screen's second truth: a station can be 'processing'
        AND operating without a valid licence. Showing only the first is
        how a manager relaxes while the station is illegal.
        """
        if not self.is_in_processing:
            return None
        previous = (
            self.periods.exclude(status=CompliancePeriod.Status.PROCESSING)
            .order_by("-expiry_date")
            .first()
        )
        if previous and previous.expiry_date and previous.expiry_date < timezone.localdate():
            return previous
        return None

    @property
    def history(self):
        return self.periods.exclude(pk=self.current_period_id).order_by("-start_date")

    def suggest_expiry(self, start_date):
        months = self.compliance_type.default_validity_months
        return start_date + relativedelta(months=months) - timedelta(days=1)


# ---------------------------------------------------------------------------
# CompliancePeriod
# ---------------------------------------------------------------------------

class CompliancePeriodQuerySet(ScopedQuerySet):
    def _scope_filter(self, station_ids):
        return self.filter(station_compliance__station_id__in=station_ids)

    def current(self):
        return self.filter(is_current=True)

    def alertable(self):
        """
        Only current periods on live stations and non-perpetual types
        ever generate an alert. Without this, every archived 2019
        certificate screams on day one of go-live.
        """
        return self.filter(
            is_current=True,
            station_compliance__station__is_active=True,
            station_compliance__compliance_type__is_active=True,
            station_compliance__compliance_type__is_perpetual=False,
        ).exclude(status=CompliancePeriod.Status.SUPERSEDED)

    def with_related(self):
        return self.select_related(
            "station_compliance__station",
            "station_compliance__compliance_type",
        )


class CompliancePeriod(TimeStampedModel):
    """
    One certificate's lifetime. A renewal creates a NEW period; it never
    edits the old one. That is where document history comes from.
    """

    class Status(models.TextChoices):
        PROCESSING = "processing", "Processing"
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        SUPERSEDED = "superseded", "Superseded"

    station_compliance = models.ForeignKey(
        StationCompliance, on_delete=models.CASCADE, related_name="periods",
    )

    certificate_number = models.CharField(max_length=80, blank=True)
    start_date = models.DateField(
        null=True, blank=True,
        help_text="Null while the renewal is still processing.",
    )
    expiry_date = models.DateField(
        null=True, blank=True, db_index=True,
        help_text="A DATE, not a timestamp. Certificates expire on a day.",
    )

    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PROCESSING, db_index=True,
    )
    is_current = models.BooleanField(default=False)

    amount_paid = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)],
        help_text="Tanzanian shillings.",
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    payment_reference = models.CharField(max_length=80, blank=True)

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="periods_submitted",
    )
    processing_started_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    objects = CompliancePeriodQuerySet.as_manager()

    class Meta:
        ordering = ["-start_date", "-created_at"]
        constraints = [
            # The guard that stops two 'active' EWURA rows for one station
            # with conflicting dates and nobody knowing which is real.
            models.UniqueConstraint(
                fields=["station_compliance"],
                condition=Q(is_current=True),
                name="one_current_period_per_obligation",
            ),
            models.CheckConstraint(
                condition=Q(expiry_date__gte=models.F("start_date"))
                | Q(start_date__isnull=True)
                | Q(expiry_date__isnull=True),
                name="expiry_after_start",
            ),
        ]
        indexes = [
            models.Index(fields=["is_current", "expiry_date"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        if self.start_date and self.expiry_date:
            return f"{self.station_compliance} {self.start_date:%Y} – {self.expiry_date:%Y}"
        return f"{self.station_compliance} (processing)"

    def clean(self):
        if self.status == self.Status.ACTIVE:
            if not self.start_date or not self.expiry_date:
                raise ValidationError(
                    "An active period needs both a start date and an expiry date."
                )

    # -- derived state ----------------------------------------------------

    @property
    def band(self):
        return bands.band_for(
            self.expiry_date,
            status=self.status,
            is_perpetual=self.station_compliance.compliance_type.is_perpetual,
        )

    @property
    def days_left(self):
        return bands.days_left(self.expiry_date)

    @property
    def is_lapsed(self):
        return (
            self.expiry_date is not None
            and self.expiry_date < timezone.localdate()
            and self.status != self.Status.SUPERSEDED
        )

    @property
    def days_in_processing(self):
        """A renewal stuck in processing for 60 days is its own problem."""
        if self.status != self.Status.PROCESSING or not self.processing_started_on:
            return None
        return (timezone.localdate() - self.processing_started_on).days

    @property
    def certificate(self):
        return self.documents.filter(
            doc_type=ComplianceDocument.DocType.CERTIFICATE
        ).first()

    @property
    def receipt(self):
        return self.documents.filter(
            doc_type=ComplianceDocument.DocType.RECEIPT
        ).first()

    @property
    def has_receipt_gap(self):
        """
        True when payment was required but no receipt was ever uploaded.
        This is the row an auditor is hunting for -- surface it at the
        collapsed level, not one click down.
        """
        if not self.station_compliance.compliance_type.requires_payment_receipt:
            return False
        return not self.documents.filter(
            doc_type=ComplianceDocument.DocType.RECEIPT
        ).exists()


# ---------------------------------------------------------------------------
# ComplianceDocument
# ---------------------------------------------------------------------------

def document_upload_path(instance, filename):
    sc = instance.period.station_compliance
    return (
        f"stations/{sc.station_id}/"
        f"{sc.compliance_type.short_code}/"
        f"{instance.period_id}/{filename}"
    )


class ComplianceDocumentQuerySet(ScopedQuerySet):
    def _scope_filter(self, station_ids):
        return self.filter(period__station_compliance__station_id__in=station_ids)


class ComplianceDocument(TimeStampedModel):
    """
    A file attached to a period. Documents are never overwritten and never
    deleted -- a renewal adds, it does not replace. 'Old receipts' is not a
    feature; it is what happens when you never delete.

    doc_type is a LABEL, not a slot: a certificate may arrive as three
    scanned pages, and a payment may be split across two receipts.
    """

    class DocType(models.TextChoices):
        CERTIFICATE = "certificate", "Certificate"
        RECEIPT = "payment_receipt", "Payment receipt"
        APPLICATION = "application", "Application form"
        INSPECTION = "inspection_report", "Inspection report"
        OTHER = "other", "Other"

    period = models.ForeignKey(
        CompliancePeriod, on_delete=models.CASCADE, related_name="documents",
    )
    doc_type = models.CharField(
        max_length=24, choices=DocType.choices, default=DocType.CERTIFICATE,
    )
    file = models.FileField(upload_to=document_upload_path, max_length=255)
    original_name = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=100, blank=True)
    size_bytes = models.PositiveIntegerField(default=0)

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="documents_uploaded",
    )

    objects = ComplianceDocumentQuerySet.as_manager()

    class Meta:
        ordering = ["doc_type", "-created_at"]
        indexes = [models.Index(fields=["period", "doc_type"])]

    def __str__(self):
        return self.original_name or self.file.name

    def get_absolute_url(self):
        return reverse("compliance:document_serve", args=[self.pk])

    @property
    def download_url(self):
        return reverse("compliance:document_serve", args=[self.pk]) + "?download=1"

    @property
    def size_display(self):
        kb = self.size_bytes / 1024
        if kb < 1024:
            return f"{kb:.0f} KB"
        return f"{kb / 1024:.1f} MB"

    @property
    def is_pdf(self):
        return self.content_type == "application/pdf" or self.file.name.lower().endswith(".pdf")
