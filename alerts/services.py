"""
Who gets warned, at what rung, on which channel.

Escalation shape: at 12 months only the person doing the work hears.
At 30 days the boss hears. That is what gives the system teeth -- the
manager knows that ignoring it becomes visible upward.
"""

import logging

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from alerts.channels import send_email, send_sms
from alerts.models import NotificationLog
from compliance.models import CompliancePeriod
from core import roles

logger = logging.getLogger("alerts")


# rung -> channels per audience
ESCALATION = {
    365: {"manager": ["inapp"], "officer": ["inapp"], "admin": []},
    180: {"manager": ["inapp", "email"], "officer": ["inapp", "email"], "admin": []},
    90:  {"manager": ["inapp", "email", "sms"], "officer": ["inapp", "email"], "admin": ["email"]},
    30:  {"manager": ["inapp", "email", "sms"], "officer": ["inapp", "email", "sms"], "admin": ["email", "sms"]},
    7:   {"manager": ["inapp", "email", "sms"], "officer": ["inapp", "email", "sms"], "admin": ["email", "sms"]},
    0:   {"manager": ["inapp", "email", "sms"], "officer": ["inapp", "email", "sms"], "admin": ["email", "sms"]},
}


def recipients_for(period):
    """Returns {"manager": [...], "officer": [...], "admin": [...]}"""
    from accounts.models import User

    station = period.station_compliance.station
    return {
        "manager": list(station.managers.filter(is_active=True)),
        "officer": list(
            User.objects.filter(
                groups__name=roles.COMPLIANCE_OFFICER, is_active=True
            ).distinct()
        ),
        "admin": list(
            User.objects.filter(
                groups__name=roles.SUPER_ADMIN, is_active=True
            ).distinct()
        ),
    }


def rung_for(period, thresholds, today=None):
    """
    The most urgent rung this period has crossed. Returns None if it has
    crossed nothing.
    """
    days = period.days_left
    if days is None:
        return None
    crossed = [t for t in sorted(thresholds) if days <= t]
    return crossed[0] if crossed else None


def is_repeating(threshold):
    return threshold in settings.REPEATING_ALERT_THRESHOLDS


def already_sent(period, recipient, channel, threshold, today):
    """
    The dedupe check. One-shot rungs fire once ever; repeating rungs
    (7, 0) fire once per day, deliberately.
    """
    dedupe_date = today if is_repeating(threshold) else None
    return NotificationLog.objects.filter(
        period=period,
        recipient=recipient,
        channel=channel,
        threshold_days=threshold,
        dedupe_date=dedupe_date,
    ).exists()


def build_message(period, threshold):
    sc = period.station_compliance
    station = sc.station
    code = sc.compliance_type.short_code
    days = period.days_left
    url = settings.SITE_BASE_URL + reverse("compliance:obligation_detail", args=[sc.pk])

    if days is not None and days < 0:
        headline = f"{code} EXPIRED {abs(days)} days ago"
    else:
        headline = f"{code} expires in {days} days"

    subject = f"{station.name}: {headline}"

    sms = (
        f"{station.name.upper()}: {code} "
        f"{'expired' if days < 0 else 'expires'} "
        f"{period.expiry_date:%d/%m/%Y} ({abs(days)}d). "
        f"Status: {period.get_status_display()}. {url}"
    )[:160]

    body = (
        f"{station.name} ({station.code})\n"
        f"{sc.compliance_type.name} — {sc.compliance_type.issuing_authority}\n\n"
        f"{headline}\n"
        f"Expiry date: {period.expiry_date:%d %b %Y}\n"
        f"Current status: {period.get_status_display()}\n"
    )
    if period.amount_paid:
        body += f"Last paid: {period.amount_paid:,.0f} TZS\n"
    body += f"\nOpen it here: {url}\n"

    return subject, body, sms


def deliver(period, recipient, channel, threshold, today, subject, body, sms):
    """
    Write the log row BEFORE sending. If the send fails we would rather
    miss one than send ninety.
    """
    dedupe_date = today if is_repeating(threshold) else None

    log = NotificationLog.objects.create(
        period=period,
        recipient=recipient,
        channel=channel,
        threshold_days=threshold,
        dedupe_date=dedupe_date,
        kind=NotificationLog.Kind.THRESHOLD,
        subject=subject,
        body=body if channel != "sms" else sms,
    )

    if channel == "email":
        send_email(recipient.email, subject, body)
    elif channel == "sms":
        send_sms(recipient.phone, sms)
    # inapp needs no delivery: the log row IS the notification.

    return log


def scan(today=None, dry_run=False):
    """
    The daily walk. Returns a summary dict.

    Suppression rules, all deliberate:
      - only current periods on live stations (alertable())
      - perpetual types never alert
      - processing suppresses SMS: somebody is already on it
    """
    today = today or timezone.localdate()
    sent = 0
    considered = 0

    periods = (
        CompliancePeriod.objects.alertable()
        .with_related()
        .select_related("station_compliance__compliance_type")
    )

    for period in periods:
        considered += 1
        ctype = period.station_compliance.compliance_type
        threshold = rung_for(period, ctype.alert_thresholds, today=today)
        if threshold is None:
            continue

        plan = ESCALATION.get(threshold)
        if plan is None:
            continue

        subject, body, sms = build_message(period, threshold)
        people = recipients_for(period)
        in_processing = period.status == CompliancePeriod.Status.PROCESSING

        for audience, channels in plan.items():
            for recipient in people[audience]:
                for channel in channels:
                    # Someone is already handling it -- nagging is noise.
                    if channel == "sms" and in_processing:
                        continue
                    if channel == "email" and not recipient.email:
                        continue
                    if channel == "sms" and not recipient.phone:
                        continue
                    if already_sent(period, recipient, channel, threshold, today):
                        continue
                    if dry_run:
                        logger.info(
                            "[dry-run] %s -> %s via %s (rung %s)",
                            period, recipient, channel, threshold,
                        )
                        sent += 1
                        continue
                    deliver(period, recipient, channel, threshold, today,
                            subject, body, sms)
                    sent += 1

    return {"considered": considered, "sent": sent, "date": today}
