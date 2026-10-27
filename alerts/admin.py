from django.contrib import admin

from alerts.models import NotificationLog


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    """
    Read-only on purpose. This table is the dedupe guard AND the audit
    record: when a licence lapses and someone asks how it happened, this
    is what shows who was warned, when, and on which channel. Editing it
    would let a duplicate alert storm through.
    """

    list_display = ("created_at", "recipient", "channel", "kind",
                    "threshold_days", "subject", "read_at")
    list_filter = ("channel", "kind", "threshold_days", "created_at")
    search_fields = ("recipient__username", "subject")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
