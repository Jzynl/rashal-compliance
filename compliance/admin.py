from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.html import format_html

from compliance.models import (
    ComplianceDocument, CompliancePeriod, ComplianceType, StationCompliance,
)

BAND_COLOURS = {
    "expired": "#7A2E0C", "critical": "#C24A12", "warning": "#B0561F",
    "active": "#0B6E3F", "safe": "#7C8A82", "processing": "#185FA5",
    "unknown": "#9AA79F",
}


def band_html(band):
    return format_html(
        '<span style="color:{};font-weight:500">{}</span>',
        BAND_COLOURS.get(band.key, "#000"), band.label,
    )


@admin.register(ComplianceType)
class ComplianceTypeAdmin(admin.ModelAdmin):
    list_display = ("short_code", "name", "issuing_authority",
                    "default_validity_months", "is_perpetual",
                    "thresholds_display", "is_active")
    list_filter = ("is_active", "is_perpetual", "requires_payment_receipt")
    search_fields = ("name", "short_code", "issuing_authority")
    ordering = ("sort_order", "name")

    fieldsets = (
        (None, {"fields": ("name", "short_code", "issuing_authority",
                           "description", "is_active", "sort_order")}),
        ("Validity", {
            "fields": ("default_validity_months", "is_perpetual",
                       "requires_payment_receipt"),
            "description": "default_validity_months only pre-fills the renewal "
                           "form. The real dates live on each period and are "
                           "always overridable.",
        }),
        ("Alerts", {
            "fields": ("alert_thresholds",),
            "description": "Days-before-expiry rungs, e.g. [365, 180, 90, 30, 7, 0]. "
                           "Fire may need only 30 days; EWURA needs six months.",
        }),
    )

    @admin.display(description="Alert rungs")
    def thresholds_display(self, obj):
        return " · ".join(str(t) for t in obj.sorted_thresholds) or "none"


class CompliancePeriodInline(admin.TabularInline):
    model = CompliancePeriod
    extra = 0
    fields = ("start_date", "expiry_date", "status", "is_current",
              "certificate_number", "amount_paid")
    readonly_fields = ("is_current",)
    ordering = ("-start_date",)
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        # Add periods from the period admin, which routes through
        # services.activate_period. Adding here would bypass it and
        # orphan the record.
        return False


@admin.register(StationCompliance)
class StationComplianceAdmin(admin.ModelAdmin):
    list_display = ("station", "compliance_type", "band_display",
                    "days_display", "expiry_display", "current_status")
    list_filter = ("compliance_type", "station__region", "station")
    search_fields = ("station__name", "station__code", "compliance_type__short_code")
    autocomplete_fields = ("station",)
    readonly_fields = ("current_period", "created_at", "updated_at")
    inlines = [CompliancePeriodInline]

    def get_queryset(self, request):
        return super().get_queryset(request).with_related()

    @admin.display(description="Band")
    def band_display(self, obj):
        return band_html(obj.band)

    @admin.display(description="Days left")
    def days_display(self, obj):
        days = obj.days_left
        return "—" if days is None else days

    @admin.display(description="Expires")
    def expiry_display(self, obj):
        p = obj.current_period
        return p.expiry_date if p and p.expiry_date else "—"

    @admin.display(description="Status")
    def current_status(self, obj):
        p = obj.current_period
        return p.get_status_display() if p else "Not set up"


class ComplianceDocumentInline(admin.TabularInline):
    model = ComplianceDocument
    extra = 0
    # 'file' is NOT shown as an editable field: its widget calls file.url to
    # render the "Currently:" link, and MEDIA_URL is None (files are private),
    # so that raises ValueError. Show a safe link through serve_document
    # instead. Uploads are done from the front end, not here.
    fields = ("doc_type", "document_link", "size_display", "uploaded_by", "created_at")
    readonly_fields = ("document_link", "size_display", "created_at")

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="File")
    def document_link(self, obj):
        if not obj.pk or not obj.file:
            return "—"
        return format_html(
            '<a href="{}" target="_blank">{}</a> '
            '(<a href="{}?download=1">download</a>)',
            reverse("compliance:document_serve", args=[obj.pk]),
            obj.original_name or obj.file.name.rsplit("/", 1)[-1],
            reverse("compliance:document_serve", args=[obj.pk]),
        )

    @admin.display(description="Size")
    def size_display(self, obj):
        return obj.size_display if obj.pk else "—"


@admin.register(CompliancePeriod)
class CompliancePeriodAdmin(admin.ModelAdmin):
    """
    Entering dates by hand must have the same effect as the renewal
    workflow, or it has no effect at all.

    is_current is deliberately NOT editable. Saving a period with status
    'Active' and both dates routes through services.activate_period,
    which supersedes the previous period and moves the obligation's
    pointer -- inside one transaction. Without this, an admin types a
    real certificate, saves, and the card silently keeps showing last
    year's date.
    """

    list_display = ("__str__", "band_display", "start_date", "expiry_date",
                    "status", "is_current", "amount_paid")
    list_filter = ("status", "is_current",
                   "station_compliance__compliance_type",
                   "station_compliance__station")
    search_fields = ("certificate_number",
                     "station_compliance__station__name")
    date_hierarchy = "expiry_date"
    readonly_fields = ("is_current", "created_at", "updated_at")
    autocomplete_fields = ("station_compliance",)
    inlines = [ComplianceDocumentInline]
    actions = ["make_current"]

    fieldsets = (
        (None, {"fields": ("station_compliance", "status", "is_current")}),
        ("Dates", {
            "fields": ("start_date", "expiry_date", "certificate_number"),
            "description": "Set status to Active with both dates filled and this "
                           "period becomes the current one; the previous period is "
                           "superseded automatically and keeps all its documents.",
        }),
        ("Payment", {"fields": ("amount_paid", "paid_at", "payment_reference")}),
        ("Other", {"fields": ("processing_started_on", "submitted_by", "notes",
                              "created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).with_related()

    def save_model(self, request, obj, form, change):
        from compliance.services import activate_period

        becoming_active = (
            obj.status == CompliancePeriod.Status.ACTIVE
            and obj.start_date and obj.expiry_date
        )

        if not becoming_active:
            super().save_model(request, obj, form, change)
            return

        if not obj.pk:
            obj.is_current = False
            super().save_model(request, obj, form, change)

        try:
            activate_period(
                obj, obj.start_date, obj.expiry_date,
                obj.certificate_number, user=request.user,
            )
            messages.success(
                request,
                f"{obj.station_compliance} is now current until "
                f"{obj.expiry_date:%d %b %Y}. Any previous period was superseded.",
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))

    @admin.action(description="Make this the current period")
    def make_current(self, request, queryset):
        from compliance.services import activate_period

        done = 0
        for period in queryset:
            if not (period.start_date and period.expiry_date):
                messages.warning(
                    request, f"{period}: needs both dates before it can be current."
                )
                continue
            try:
                activate_period(period, period.start_date, period.expiry_date,
                                period.certificate_number, user=request.user)
                done += 1
            except ValidationError as exc:
                messages.error(request, f"{period}: {'; '.join(exc.messages)}")
        if done:
            messages.success(request, f"{done} period(s) made current.")

    @admin.display(description="Band")
    def band_display(self, obj):
        return band_html(obj.band)