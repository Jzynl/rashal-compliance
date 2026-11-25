from django.contrib import admin

from payroll.models import PayLine, PayRun


class PayLineInline(admin.TabularInline):
    model = PayLine
    extra = 0
    fields = ("beneficiary_name", "beneficiary_account", "amount", "include")


@admin.register(PayRun)
class PayRunAdmin(admin.ModelAdmin):
    list_display = ("__str__", "reference", "status", "headcount", "total_amount", "created_by")
    list_filter = ("status", "year", "month")
    inlines = [PayLineInline]


@admin.register(PayLine)
class PayLineAdmin(admin.ModelAdmin):
    list_display = ("beneficiary_name", "pay_run", "amount", "include")
    list_filter = ("pay_run", "include")
    search_fields = ("beneficiary_name", "beneficiary_account")


from payroll.models import RetrenchmentBatch, RetrenchmentPayment  # noqa: E402


class RetrPaymentInline(admin.TabularInline):
    model = RetrenchmentPayment
    extra = 0
    fields = ("name", "account_no", "amount", "bank", "branch", "include")


@admin.register(RetrenchmentBatch)
class RetrenchmentBatchAdmin(admin.ModelAdmin):
    list_display = ("__str__", "station", "year", "status", "headcount", "total_amount")
    list_filter = ("status", "year", "station")
    inlines = [RetrPaymentInline]


@admin.register(RetrenchmentPayment)
class RetrenchmentPaymentAdmin(admin.ModelAdmin):
    list_display = ("name", "batch", "amount", "include")
    search_fields = ("name", "account_no")
