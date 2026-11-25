from django.contrib import admin

from audit.models import (Audit, AuditFinding, AuditResponse,
                          ChecklistItem, ChecklistSection, ChecklistTemplate)


class ChecklistItemInline(admin.TabularInline):
    model = ChecklistItem
    extra = 1
    fields = ("order", "text")


@admin.register(ChecklistSection)
class ChecklistSectionAdmin(admin.ModelAdmin):
    list_display = ("__str__", "template", "order")
    list_filter = ("template",)
    inlines = [ChecklistItemInline]


class ChecklistSectionInline(admin.TabularInline):
    model = ChecklistSection
    extra = 1
    fields = ("order", "label", "title")
    show_change_link = True


@admin.register(ChecklistTemplate)
class ChecklistTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "order", "is_active", "item_count")
    inlines = [ChecklistSectionInline]


class AuditFindingInline(admin.TabularInline):
    model = AuditFinding
    extra = 0
    fields = ("description", "category", "status", "responsible", "due_date")


@admin.register(Audit)
class AuditAdmin(admin.ModelAdmin):
    list_display = ("title", "station", "template", "audit_date", "status",
                    "total_findings_count", "open_findings_count")
    list_filter = ("status", "station", "template")
    inlines = [AuditFindingInline]


@admin.register(AuditFinding)
class AuditFindingAdmin(admin.ModelAdmin):
    list_display = ("__str__", "audit", "category", "status", "due_date")
    list_filter = ("status", "category")


@admin.register(AuditResponse)
class AuditResponseAdmin(admin.ModelAdmin):
    list_display = ("audit", "item", "answer")
    list_filter = ("answer",)
