from django.contrib import admin

from leave.models import LeaveBalance, LeaveRecord, LeaveType


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "is_paid", "annual_entitlement_days", "is_active")
    list_filter = ("is_paid", "is_active")


@admin.register(LeaveBalance)
class LeaveBalanceAdmin(admin.ModelAdmin):
    list_display = ("employee", "leave_type", "year", "allowed",
                    "taken_first", "taken_second", "remaining", "status")
    list_filter = ("year", "leave_type", "status")
    search_fields = ("employee__first_name", "employee__last_name")


@admin.register(LeaveRecord)
class LeaveRecordAdmin(admin.ModelAdmin):
    list_display = ("employee", "leave_type", "start_date", "end_date", "days", "status")
    list_filter = ("status", "leave_type")
