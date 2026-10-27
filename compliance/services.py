"""
State transitions.

Rule: status is set by events, not by a nightly job flipping things.
The only automatic transition is active -> expired when the date passes.
Everything else happens because a human did something.

All transitions are transactional. The one_current_period constraint
means a botched swap raises rather than corrupts.
"""

import logging

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from compliance.models import CompliancePeriod, ComplianceDocument

logger = logging.getLogger(__name__)


@transaction.atomic
def start_renewal(station_compliance, user, amount=None, reference="", notes=""):
    """
    Step 1: a renewal has begun. No certificate yet, so no dates yet.
    The old period stays current until the new certificate lands -- the
    station is still operating on the old licence (or on nothing).
    """
    existing = station_compliance.periods.filter(
        status=CompliancePeriod.Status.PROCESSING
    ).first()
    if existing:
        raise ValidationError("A renewal is already in progress for this compliance.")

    return CompliancePeriod.objects.create(
        station_compliance=station_compliance,
        status=CompliancePeriod.Status.PROCESSING,
        is_current=False,
        amount_paid=amount,
        payment_reference=reference,
        paid_at=timezone.now() if amount else None,
        processing_started_on=timezone.localdate(),
        submitted_by=user,
        notes=notes,
    )


@transaction.atomic
def record_payment(period, amount, reference="", user=None):
    """Step 2: payment made. Receipt is uploaded separately."""
    period.amount_paid = amount
    period.payment_reference = reference
    period.paid_at = timezone.now()
    if user and not period.submitted_by:
        period.submitted_by = user
    period.full_clean()
    period.save()
    return period


@transaction.atomic
def activate_period(period, start_date, expiry_date, certificate_number="", user=None):
    """
    Step 3: the certificate arrived.

    The new period becomes current, the old one is superseded, and the
    obligation's pointer moves. All of it or none of it.
    """
    if expiry_date < start_date:
        raise ValidationError("Expiry date cannot be before the start date.")

    sc = period.station_compliance

    # Lock the obligation so two officers cannot activate at once.
    sc = type(sc).objects.select_for_update().get(pk=sc.pk)

    previous = sc.current_period

    period.start_date = start_date
    period.expiry_date = expiry_date
    period.certificate_number = certificate_number
    period.status = CompliancePeriod.Status.ACTIVE
    if user and not period.submitted_by:
        period.submitted_by = user
    period.full_clean(exclude=["is_current"])

    if previous and previous.pk != period.pk:
        previous.is_current = False
        previous.status = CompliancePeriod.Status.SUPERSEDED
        previous.save(update_fields=["is_current", "status", "updated_at"])

    period.is_current = True
    period.save()

    sc.current_period = period
    sc.save(update_fields=["current_period", "updated_at"])

    logger.info("Activated %s (%s to %s)", sc, start_date, expiry_date)
    return period


@transaction.atomic
def attach_document(period, django_file, doc_type, user=None):
    """Add a document. Never replaces an existing one."""
    doc = ComplianceDocument(
        period=period,
        doc_type=doc_type,
        file=django_file,
        original_name=getattr(django_file, "name", "")[:255],
        content_type=getattr(django_file, "content_type", "")[:100],
        size_bytes=getattr(django_file, "size", 0),
        uploaded_by=user,
    )
    doc.full_clean(exclude=["file"])
    doc.save()
    return doc


def expire_lapsed_periods(today=None):
    """
    The ONLY automatic transition in the system.

    Called by the daily scan. Everything else is human-driven.
    """
    today = today or timezone.localdate()
    qs = CompliancePeriod.objects.filter(
        is_current=True,
        status=CompliancePeriod.Status.ACTIVE,
        expiry_date__lt=today,
    )
    count = qs.update(status=CompliancePeriod.Status.EXPIRED, updated_at=timezone.now())
    if count:
        logger.info("Marked %s period(s) expired", count)
    return count
