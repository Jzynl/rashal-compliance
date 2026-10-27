from django.conf import settings


def branding(request):
    ctx = {"BRAND": settings.BRAND, "SITE_BASE_URL": settings.SITE_BASE_URL}

    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        from alerts.models import NotificationLog
        ctx["alert_count"] = NotificationLog.objects.filter(
            recipient=user, read_at__isnull=True, channel="inapp",
        ).count()
    return ctx
