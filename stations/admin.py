from django.contrib import admin
from django.utils.html import format_html

from stations.models import Station


@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "region", "district",
                    "status_badge", "has_coordinates", "is_active")
    list_filter = ("is_active", "region")
    search_fields = ("name", "code", "district")
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("name", "code", "is_active")}),
        ("Location", {"fields": ("region", "district", "address",
                                 "latitude", "longitude")}),
        ("Other", {"fields": ("commissioned_on", "notes",
                              "created_at", "updated_at")}),
    )

    @admin.display(description="Worst status")
    def status_badge(self, obj):
        band = obj.worst_band()
        colours = {
            "expired": "#7A2E0C", "critical": "#C24A12", "warning": "#B0561F",
            "active": "#0B6E3F", "safe": "#7C8A82", "processing": "#185FA5",
            "unknown": "#9AA79F",
        }
        return format_html(
            '<span style="color:{};font-weight:500">{}</span>',
            colours.get(band.key, "#000"), band.label,
        )
