from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from accounts.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "get_full_name", "email", "phone",
                    "role_label", "station_list", "is_active")
    list_filter = ("groups", "is_active", "stations")
    search_fields = ("username", "first_name", "last_name", "email", "phone")
    filter_horizontal = ("groups", "user_permissions", "stations")

    fieldsets = BaseUserAdmin.fieldsets + (
        ("Compliance system", {
            "fields": ("phone", "job_title", "stations", "receives_digest"),
            "description": "Stations is many-to-many: a regional manager covers "
                           "several. Leave empty for super admins and officers, "
                           "who see everything by role.",
        }),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Compliance system", {"fields": ("email", "phone", "stations")}),
    )

    @admin.display(description="Stations")
    def station_list(self, obj):
        names = list(obj.stations.values_list("name", flat=True)[:3])
        extra = obj.stations.count() - len(names)
        text = ", ".join(names) or "—"
        return f"{text} +{extra}" if extra > 0 else text
