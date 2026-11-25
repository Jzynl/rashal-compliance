from datetime import date

from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from core import roles
from core.mixins import RoleRequiredMixin
from leave.forms import LeaveBalanceForm, LeaveTypeForm
from leave.models import LeaveBalance, LeaveType

LEAVE_ROLES = {roles.SUPER_ADMIN, roles.HR_MANAGER}


class LeaveAccessMixin(RoleRequiredMixin):
    allowed_roles = LEAVE_ROLES


def _current_year():
    return date.today().year


# --- Balances (the main view, matching the leave sheets) ------------------
class BalanceListView(LeaveAccessMixin, ListView):
    model = LeaveBalance
    template_name = "leave/balance_list.html"
    context_object_name = "balances"
    extra_context = {"nav": "leave"}

    def _year(self):
        try:
            return int(self.request.GET.get("year", _current_year()))
        except (TypeError, ValueError):
            return _current_year()

    def _type(self):
        t = self.request.GET.get("type")
        if t:
            return LeaveType.objects.filter(pk=t).first()
        return LeaveType.objects.filter(is_active=True).order_by("name").first()

    def get_queryset(self):
        qs = (LeaveBalance.objects
              .select_related("employee", "employee__station", "leave_type")
              .filter(year=self._year()))
        lt = self._type()
        if lt:
            qs = qs.filter(leave_type=lt)
        return qs.order_by("employee__station__name", "employee__first_name")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["types"] = LeaveType.objects.filter(is_active=True)
        ctx["sel_type"] = self._type()
        ctx["year"] = self._year()
        ctx["years"] = range(_current_year() + 1, _current_year() - 4, -1)
        return ctx


class BalanceCreateView(LeaveAccessMixin, CreateView):
    model = LeaveBalance
    form_class = LeaveBalanceForm
    template_name = "leave/balance_form.html"
    extra_context = {"nav": "leave", "mode": "add"}

    def form_valid(self, form):
        # Default the allowance from the leave type if left blank.
        if not form.instance.allowed and form.instance.leave_type_id:
            form.instance.allowed = form.instance.leave_type.annual_entitlement_days or 0
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("leave:balance_list") + f"?year={self.object.year}&type={self.object.leave_type_id}"


class BalanceUpdateView(LeaveAccessMixin, UpdateView):
    model = LeaveBalance
    form_class = LeaveBalanceForm
    template_name = "leave/balance_form.html"
    context_object_name = "balance"
    extra_context = {"nav": "leave", "mode": "edit"}

    def get_success_url(self):
        return reverse("leave:balance_list") + f"?year={self.object.year}&type={self.object.leave_type_id}"


class BalanceDeleteView(LeaveAccessMixin, DeleteView):
    model = LeaveBalance
    template_name = "leave/balance_confirm_delete.html"
    context_object_name = "balance"
    extra_context = {"nav": "leave"}
    success_url = reverse_lazy("leave:balance_list")


# --- Types ----------------------------------------------------------------
class LeaveTypeListView(LeaveAccessMixin, ListView):
    model = LeaveType
    template_name = "leave/type_list.html"
    context_object_name = "types"
    extra_context = {"nav": "leave"}


class LeaveTypeCreateView(LeaveAccessMixin, CreateView):
    model = LeaveType
    form_class = LeaveTypeForm
    template_name = "leave/type_form.html"
    extra_context = {"nav": "leave", "mode": "add"}
    success_url = reverse_lazy("leave:type_list")


class LeaveTypeUpdateView(LeaveAccessMixin, UpdateView):
    model = LeaveType
    form_class = LeaveTypeForm
    template_name = "leave/type_form.html"
    context_object_name = "type"
    extra_context = {"nav": "leave", "mode": "edit"}
    success_url = reverse_lazy("leave:type_list")
