from django.contrib import admin

from foundation.models import (Department, Employee, EmployeeCredential,
                               Organisation, Position)


@admin.register(EmployeeCredential)
class EmployeeCredentialAdmin(admin.ModelAdmin):
    list_display = ("employee", "kind", "title", "provider", "issue_date", "expiry_date")
    list_filter = ("kind",)
    search_fields = ("title", "provider", "employee__first_name", "employee__last_name")


@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    list_display = ("name", "tin", "city", "phone")
    search_fields = ("name", "legal_name", "tin")


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "organisation")
    list_filter = ("organisation",)
    search_fields = ("name",)


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ("title", "department")
    list_filter = ("department",)
    search_fields = ("title",)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("full_name", "job_title", "station", "employment_category",
                    "is_active", "has_login")
    list_filter = ("is_active", "employment_category", "station", "department")
    search_fields = ("first_name", "middle_name", "last_name", "national_id")
    autocomplete_fields = ("station",) if False else ()
    fieldsets = (
        ("Person", {
            "fields": ("first_name", "middle_name", "last_name", "gender",
                       "date_of_birth", "national_id", "phone"),
        }),
        ("Employment", {
            "fields": ("organisation", "station", "department", "position",
                       "job_title", "employment_category",
                       "date_joined", "date_left", "is_active", "user"),
        }),
        ("Banking (sensitive)", {
            "classes": ("collapse",),
            "fields": ("bank_name", "bank_branch", "bank_account_number"),
        }),
        ("Statutory membership", {
            "classes": ("collapse",),
            "fields": ("nssf_number", "nhif_number", "wcf_number", "tin"),
        }),
    )

    @admin.display(description="Login", boolean=True)
    def has_login(self, obj):
        return obj.user_id is not None
