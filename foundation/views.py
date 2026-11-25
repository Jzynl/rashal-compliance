from django.urls import reverse_lazy
from django.views.generic import (CreateView, DeleteView, DetailView, ListView, UpdateView)

from core import roles
from core.mixins import RoleRequiredMixin
from foundation.forms import EmployeeCredentialForm, EmployeeForm
from foundation.models import Employee, EmployeeCredential, Organisation

# People management is HR-only for now.
HR_ONLY = {roles.SUPER_ADMIN, roles.HR_MANAGER}


class EmployeeAccessMixin(RoleRequiredMixin):
    allowed_roles = HR_ONLY


class EmployeeListView(EmployeeAccessMixin, ListView):
    model = Employee
    template_name = "foundation/employee_list.html"
    context_object_name = "employees"
    extra_context = {"nav": "people"}

    def get_queryset(self):
        qs = Employee.objects.with_related().order_by(
            "-is_active", "first_name", "last_name"
        )
        org = self.request.GET.get("company")
        if org:
            qs = qs.filter(organisation_id=org)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["companies"] = Organisation.objects.all()
        ctx["sel_company"] = self.request.GET.get("company", "")
        return ctx


class EmployeeDetailView(EmployeeAccessMixin, DetailView):
    model = Employee
    template_name = "foundation/employee_detail.html"
    context_object_name = "emp"
    extra_context = {"nav": "people"}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["credentials"] = self.object.credentials.all()
        return ctx


class EmployeeCreateView(EmployeeAccessMixin, CreateView):
    model = Employee
    form_class = EmployeeForm
    template_name = "foundation/employee_form.html"
    extra_context = {"nav": "people", "mode": "add"}

    def get_success_url(self):
        return reverse_lazy("foundation:employee_detail", args=[self.object.pk])


class EmployeeUpdateView(EmployeeAccessMixin, UpdateView):
    model = Employee
    form_class = EmployeeForm
    template_name = "foundation/employee_form.html"
    context_object_name = "emp"
    extra_context = {"nav": "people", "mode": "edit"}

    def get_success_url(self):
        return reverse_lazy("foundation:employee_detail", args=[self.object.pk])


# -- Statutory membership (reads existing Employee fields) -----------------
class StatutoryListView(EmployeeAccessMixin, ListView):
    model = Employee
    template_name = "foundation/statutory_list.html"
    context_object_name = "employees"
    extra_context = {"nav": "people"}

    def get_queryset(self):
        return Employee.objects.active().with_related().order_by(
            "station__name", "first_name", "last_name")


# -- Training & certifications --------------------------------------------
class CredentialListView(EmployeeAccessMixin, ListView):
    model = EmployeeCredential
    template_name = "foundation/credential_list.html"
    context_object_name = "credentials"
    extra_context = {"nav": "people"}

    def get_queryset(self):
        qs = EmployeeCredential.objects.select_related("employee")
        kind = self.request.GET.get("kind")
        if kind in ("training", "certification"):
            qs = qs.filter(kind=kind)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["kind"] = self.request.GET.get("kind", "")
        return ctx


class CredentialCreateView(EmployeeAccessMixin, CreateView):
    model = EmployeeCredential
    form_class = EmployeeCredentialForm
    template_name = "foundation/credential_form.html"
    extra_context = {"nav": "people", "mode": "add"}

    def get_initial(self):
        initial = super().get_initial()
        emp = self.request.GET.get("employee")
        if emp:
            initial["employee"] = emp
        return initial

    def get_success_url(self):
        return reverse_lazy("foundation:employee_detail", args=[self.object.employee_id])


class CredentialUpdateView(EmployeeAccessMixin, UpdateView):
    model = EmployeeCredential
    form_class = EmployeeCredentialForm
    template_name = "foundation/credential_form.html"
    context_object_name = "credential"
    extra_context = {"nav": "people", "mode": "edit"}

    def get_success_url(self):
        return reverse_lazy("foundation:employee_detail", args=[self.object.employee_id])


class CredentialDeleteView(EmployeeAccessMixin, DeleteView):
    model = EmployeeCredential
    template_name = "foundation/credential_confirm_delete.html"
    context_object_name = "credential"
    extra_context = {"nav": "people"}

    def get_success_url(self):
        return reverse_lazy("foundation:employee_detail", args=[self.object.employee_id])
