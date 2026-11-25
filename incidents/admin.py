from django.contrib import admin

from incidents.models import Incident


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ("title", "station", "category", "severity", "status", "occurred_on")
    list_filter = ("status", "category", "severity", "station")
    search_fields = ("title", "description", "reported_by")
    date_hierarchy = "occurred_on"
