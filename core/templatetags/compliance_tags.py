from django import template

from core.bands import band_for

register = template.Library()


@register.simple_tag
def band_of(period):
    """Resolve a CompliancePeriod (or None) to its Band."""
    if period is None:
        from core.bands import UNKNOWN
        return UNKNOWN
    return period.band


@register.filter
def days_display(value):
    """
    Render signed days remaining. Keeps expired as a negative number so it
    stays comparable with every other card in the same column.
    """
    if value is None:
        return "—"
    return f"{value}" if value >= 0 else f"\u2212{abs(value)}"


@register.filter
def tzs(value):
    """Format an amount in Tanzanian shillings."""
    if value is None:
        return "—"
    return f"{value:,.0f} TZS"
