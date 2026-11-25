import csv
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView, View

from core import roles
from core.mixins import RoleRequiredMixin
from foundation.models import Employee
from payroll.forms import PayLineForm, PayRunForm
from payroll.models import PayLine, PayRun

# Bank file column order, matching the NMB sample exactly.
BANK_COLUMNS = [
    "Beneficiary_Name", "Amount", "Beneficiary_Account",
    "Payment Type", "Destination", "Narration", "Ownreference",
]

PAYROLL_ROLES = {roles.SUPER_ADMIN, roles.PAYROLL_OFFICER}


class PayrollAccessMixin(RoleRequiredMixin):
    allowed_roles = PAYROLL_ROLES


def _bank_rows(run):
    """One list-of-values per included line, in BANK_COLUMNS order."""
    rows = []
    for line in run.included_lines.all():
        rows.append([
            line.beneficiary_name,
            line.amount,
            line.beneficiary_account,
            run.payment_type,
            run.destination,
            line.narration_value,
            run.reference,
        ])
    return rows


# --------------------------------------------------------------------------
# Runs
# --------------------------------------------------------------------------
class RunListView(PayrollAccessMixin, ListView):
    model = PayRun
    template_name = "payroll/run_list.html"
    context_object_name = "runs"
    extra_context = {"nav": "payroll"}


class RunCreateView(PayrollAccessMixin, CreateView):
    model = PayRun
    form_class = PayRunForm
    template_name = "payroll/run_form.html"
    extra_context = {"nav": "payroll", "mode": "add"}

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("payroll:run_detail", args=[self.object.pk])


class RunUpdateView(PayrollAccessMixin, UpdateView):
    model = PayRun
    form_class = PayRunForm
    template_name = "payroll/run_form.html"
    extra_context = {"nav": "payroll", "mode": "edit"}

    def get_success_url(self):
        return reverse("payroll:run_detail", args=[self.object.pk])


class RunDetailView(PayrollAccessMixin, DetailView):
    model = PayRun
    template_name = "payroll/run_detail.html"
    context_object_name = "run"
    extra_context = {"nav": "payroll"}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["lines"] = self.object.lines.all()
        return ctx


# --------------------------------------------------------------------------
# Lines
# --------------------------------------------------------------------------
class LineCreateView(PayrollAccessMixin, CreateView):
    model = PayLine
    form_class = PayLineForm
    template_name = "payroll/line_form.html"
    extra_context = {"nav": "payroll", "mode": "add"}

    def dispatch(self, request, *args, **kwargs):
        self.run = get_object_or_404(PayRun, pk=kwargs["run_pk"])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.pay_run = self.run
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["run"] = self.run
        return ctx

    def get_success_url(self):
        return reverse("payroll:run_detail", args=[self.run.pk])


class LineUpdateView(PayrollAccessMixin, UpdateView):
    model = PayLine
    form_class = PayLineForm
    template_name = "payroll/line_form.html"
    context_object_name = "line"
    extra_context = {"nav": "payroll", "mode": "edit"}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["run"] = self.object.pay_run
        return ctx

    def get_success_url(self):
        return reverse("payroll:run_detail", args=[self.object.pay_run.pk])


class LineDeleteView(PayrollAccessMixin, View):
    def post(self, request, pk):
        line = get_object_or_404(PayLine, pk=pk)
        run_pk = line.pay_run_id
        if line.pay_run.is_final:
            messages.error(request, "This run is finalised and cannot be edited.")
        else:
            line.delete()
            messages.success(request, "Line removed.")
        return redirect("payroll:run_detail", pk=run_pk)


# --------------------------------------------------------------------------
# Bulk actions on a run
# --------------------------------------------------------------------------
class PopulateFromEmployeesView(PayrollAccessMixin, View):
    """Add a line for every active employee who has a bank account number."""

    def post(self, request, run_pk):
        run = get_object_or_404(PayRun, pk=run_pk)
        if run.is_final:
            messages.error(request, "This run is finalised and cannot be edited.")
            return redirect("payroll:run_detail", pk=run.pk)

        existing = set(run.lines.exclude(employee=None).values_list("employee_id", flat=True))
        added = 0
        for emp in Employee.objects.active().exclude(bank_account_number=""):
            if emp.pk in existing:
                continue
            PayLine.objects.create(
                pay_run=run, employee=emp,
                beneficiary_name=emp.full_name,
                beneficiary_account=emp.bank_account_number,
                amount=Decimal("0"),
            )
            added += 1
        messages.success(request, f"Added {added} employee(s). Enter each person's amount.")
        return redirect("payroll:run_detail", pk=run.pk)


class CopyFromPreviousView(PayrollAccessMixin, View):
    """Clone the lines (names, accounts, amounts) from the most recent other run."""

    def post(self, request, run_pk):
        run = get_object_or_404(PayRun, pk=run_pk)
        if run.is_final:
            messages.error(request, "This run is finalised and cannot be edited.")
            return redirect("payroll:run_detail", pk=run.pk)

        previous = (
            PayRun.objects.exclude(pk=run.pk)
            .filter(lines__isnull=False).distinct().first()
        )
        if not previous:
            messages.error(request, "There is no earlier run to copy from.")
            return redirect("payroll:run_detail", pk=run.pk)

        copied = 0
        for line in previous.lines.all():
            PayLine.objects.create(
                pay_run=run, employee=line.employee,
                beneficiary_name=line.beneficiary_name,
                beneficiary_account=line.beneficiary_account,
                amount=line.amount, narration=line.narration, include=line.include,
            )
            copied += 1
        messages.success(request, f"Copied {copied} line(s) from {previous}. Adjust amounts as needed.")
        return redirect("payroll:run_detail", pk=run.pk)


class FinaliseView(PayrollAccessMixin, View):
    def post(self, request, run_pk):
        run = get_object_or_404(PayRun, pk=run_pk)
        run.status = PayRun.Status.FINAL
        run.save(update_fields=["status", "updated_at"])
        messages.success(request, "Run finalised. It is now locked for editing.")
        return redirect("payroll:run_detail", pk=run.pk)


class ReopenView(PayrollAccessMixin, View):
    def post(self, request, run_pk):
        run = get_object_or_404(PayRun, pk=run_pk)
        run.status = PayRun.Status.DRAFT
        run.save(update_fields=["status", "updated_at"])
        messages.success(request, "Run reopened for editing.")
        return redirect("payroll:run_detail", pk=run.pk)


# --------------------------------------------------------------------------
# Exports -- the NMB bank file
# --------------------------------------------------------------------------
def _filename(run, ext):
    return f"salary_{run.reference or run.month}_{run.year}_NMB.{ext}"


class ExportCsvView(PayrollAccessMixin, View):
    def get(self, request, run_pk):
        run = get_object_or_404(PayRun, pk=run_pk)
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = f'attachment; filename="{_filename(run, "csv")}"'
        writer = csv.writer(resp)
        writer.writerow(BANK_COLUMNS)
        for row in _bank_rows(run):
            # amount as a plain number, no decimals for whole values (matches NMB sample)
            r = list(row)
            amt = Decimal(r[1])
            r[1] = str(int(amt)) if amt == amt.to_integral_value() else f"{amt:f}"
            writer.writerow(r)
        return resp


class ExportXlsxView(PayrollAccessMixin, View):
    def get(self, request, run_pk):
        run = get_object_or_404(PayRun, pk=run_pk)
        try:
            import openpyxl
        except ImportError:
            messages.error(
                request,
                "Excel export needs the openpyxl package (pip install openpyxl). "
                "Use the CSV download instead.",
            )
            return redirect("payroll:run_detail", pk=run.pk)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"{run.get_month_display()[:3].upper()} {run.year}"
        ws.append(BANK_COLUMNS)
        for row in _bank_rows(run):
            r = list(row)
            r[1] = int(r[1]) if r[1] == r[1].to_integral_value() else float(r[1])
            ws.append(r)

        resp = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        resp["Content-Disposition"] = f'attachment; filename="{_filename(run, "xlsx")}"'
        wb.save(resp)
        return resp


# --------------------------------------------------------------------------
# Retrenchment (severance) payouts
# --------------------------------------------------------------------------
from payroll.forms import RetrenchmentBatchForm, RetrenchmentPaymentForm  # noqa: E402
from payroll.models import RetrenchmentBatch, RetrenchmentPayment  # noqa: E402

RETR_COLUMNS = ["ID", "Name", "AccountNo", "Amount", "Bank", "Branch", "Description"]


def _retr_rows(batch):
    rows = []
    for i, p in enumerate(batch.included_payments.all(), start=1):
        rows.append([i, p.name, p.account_no, p.amount, p.bank, p.branch, p.description_value])
    return rows


class RetrListView(PayrollAccessMixin, ListView):
    model = RetrenchmentBatch
    template_name = "payroll/retr_list.html"
    context_object_name = "batches"
    extra_context = {"nav": "payroll"}


class RetrCreateView(PayrollAccessMixin, CreateView):
    model = RetrenchmentBatch
    form_class = RetrenchmentBatchForm
    template_name = "payroll/retr_form.html"
    extra_context = {"nav": "payroll", "mode": "add"}

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("payroll:retr_detail", args=[self.object.pk])


class RetrUpdateView(PayrollAccessMixin, UpdateView):
    model = RetrenchmentBatch
    form_class = RetrenchmentBatchForm
    template_name = "payroll/retr_form.html"
    extra_context = {"nav": "payroll", "mode": "edit"}

    def get_success_url(self):
        return reverse("payroll:retr_detail", args=[self.object.pk])


class RetrDetailView(PayrollAccessMixin, DetailView):
    model = RetrenchmentBatch
    template_name = "payroll/retr_detail.html"
    context_object_name = "batch"
    extra_context = {"nav": "payroll"}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["payments"] = self.object.payments.all()
        return ctx


class RetrPaymentCreateView(PayrollAccessMixin, CreateView):
    model = RetrenchmentPayment
    form_class = RetrenchmentPaymentForm
    template_name = "payroll/retr_payment_form.html"
    extra_context = {"nav": "payroll", "mode": "add"}

    def dispatch(self, request, *args, **kwargs):
        self.batch = get_object_or_404(RetrenchmentBatch, pk=kwargs["batch_pk"])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.batch = self.batch
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["batch"] = self.batch
        return ctx

    def get_success_url(self):
        return reverse("payroll:retr_detail", args=[self.batch.pk])


class RetrPaymentUpdateView(PayrollAccessMixin, UpdateView):
    model = RetrenchmentPayment
    form_class = RetrenchmentPaymentForm
    template_name = "payroll/retr_payment_form.html"
    context_object_name = "payment"
    extra_context = {"nav": "payroll", "mode": "edit"}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["batch"] = self.object.batch
        return ctx

    def get_success_url(self):
        return reverse("payroll:retr_detail", args=[self.object.batch.pk])


class RetrPaymentDeleteView(PayrollAccessMixin, View):
    def post(self, request, pk):
        p = get_object_or_404(RetrenchmentPayment, pk=pk)
        batch_pk = p.batch_id
        if p.batch.is_final:
            messages.error(request, "This batch is finalised and cannot be edited.")
        else:
            p.delete()
            messages.success(request, "Payment removed.")
        return redirect("payroll:retr_detail", pk=batch_pk)


class RetrFinaliseView(PayrollAccessMixin, View):
    def post(self, request, batch_pk):
        b = get_object_or_404(RetrenchmentBatch, pk=batch_pk)
        b.status = RetrenchmentBatch.Status.FINAL
        b.save(update_fields=["status", "updated_at"])
        messages.success(request, "Batch finalised.")
        return redirect("payroll:retr_detail", pk=b.pk)


class RetrReopenView(PayrollAccessMixin, View):
    def post(self, request, batch_pk):
        b = get_object_or_404(RetrenchmentBatch, pk=batch_pk)
        b.status = RetrenchmentBatch.Status.DRAFT
        b.save(update_fields=["status", "updated_at"])
        messages.success(request, "Batch reopened.")
        return redirect("payroll:retr_detail", pk=b.pk)


class RetrExportCsvView(PayrollAccessMixin, View):
    def get(self, request, batch_pk):
        b = get_object_or_404(RetrenchmentBatch, pk=batch_pk)
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = f'attachment; filename="retrenchment_{b.year}.csv"'
        w = csv.writer(resp)
        w.writerow(RETR_COLUMNS)
        for row in _retr_rows(b):
            r = list(row)
            amt = Decimal(r[3])
            r[3] = str(int(amt)) if amt == amt.to_integral_value() else f"{amt:f}"
            w.writerow(r)
        return resp


class RetrExportXlsxView(PayrollAccessMixin, View):
    def get(self, request, batch_pk):
        b = get_object_or_404(RetrenchmentBatch, pk=batch_pk)
        try:
            import openpyxl
        except ImportError:
            messages.error(request, "Excel export needs openpyxl. Use CSV instead.")
            return redirect("payroll:retr_detail", pk=b.pk)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"RET {b.year}"
        ws.append(RETR_COLUMNS)
        for row in _retr_rows(b):
            r = list(row)
            amt = Decimal(r[3])
            r[3] = int(amt) if amt == amt.to_integral_value() else float(amt)
            ws.append(r)
        resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        resp["Content-Disposition"] = f'attachment; filename="retrenchment_{b.year}.xlsx"'
        wb.save(resp)
        return resp
