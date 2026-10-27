"""
The single source of truth for compliance urgency.

Every colour, badge, alert rung, SMS tone and digest row in this project
resolves through band_for(). Nothing else is allowed to decide urgency.

If you find yourself writing `if days < 90` anywhere outside this module,
stop: that is how the UI and the alerts drift apart.
"""

from dataclasses import dataclass
from datetime import date

from django.conf import settings
from django.utils import timezone


@dataclass(frozen=True)
class Band:
    key: str
    label: str          # what the user reads
    css: str            # css class suffix -> .band-expired, .band-critical, ...
    icon: str           # tabler icon name
    rank: int           # sort order: lower = more urgent
    tone: str           # "danger" | "warning" | "ok" | "neutral" | "info"


EXPIRED = Band("expired", "Expired", "expired", "alert-octagon", 0, "danger")
CRITICAL = Band("critical", "Critical", "critical", "clock", 1, "danger")
WARNING = Band("warning", "Expiring soon", "warning", "clock", 2, "warning")
ACTIVE = Band("active", "Active", "active", "check", 3, "ok")
SAFE = Band("safe", "Active", "safe", "check", 4, "neutral")
PROCESSING = Band("processing", "Processing", "processing", "hourglass", 5, "info")
UNKNOWN = Band("unknown", "Not set up", "unknown", "help-circle", 6, "neutral")

ALL_BANDS = [EXPIRED, CRITICAL, WARNING, ACTIVE, SAFE, PROCESSING, UNKNOWN]
BANDS_BY_KEY = {b.key: b for b in ALL_BANDS}


def days_left(expiry_date, today=None):
    """Signed days until expiry. Negative means already lapsed."""
    if expiry_date is None:
        return None
    today = today or timezone.localdate()
    if isinstance(expiry_date, date) and not isinstance(expiry_date, type(today)):
        pass
    return (expiry_date - today).days


def band_for(expiry_date, status=None, is_perpetual=False, today=None):
    """
    Resolve a period to its urgency band.

    expiry_date   -- date or None
    status        -- CompliancePeriod.Status value, or None
    is_perpetual  -- True for obligations that never expire (e.g. TRA TIN)
    """
    from compliance.models import CompliancePeriod  # local import: avoids cycle

    if status == CompliancePeriod.Status.PROCESSING:
        return PROCESSING

    if is_perpetual:
        return SAFE

    if expiry_date is None:
        return UNKNOWN

    remaining = days_left(expiry_date, today=today)

    if remaining < 0:
        return EXPIRED
    if remaining <= settings.BAND_CRITICAL_DAYS:
        return CRITICAL
    if remaining <= settings.BAND_WARNING_DAYS:
        return WARNING
    if remaining <= settings.BAND_ACTIVE_DAYS:
        return ACTIVE
    return SAFE
