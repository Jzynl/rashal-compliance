from django.urls import reverse_lazy
from django.views.generic import (CreateView, DeleteView, DetailView, ListView, UpdateView)

from core import roles
from core.mixins import RoleRequiredMixin
from incidents.forms import IncidentForm
from incidents.models import Incident

INCIDENT_ROLES = {roles.SUPER_ADMIN, roles.COMPLIANCE_OFFICER, roles.AUDITOR, roles.STATION_MANAGER}


class IncidentAccessMixin(RoleRequiredMixin):
    allowed_roles = INCIDENT_ROLES


class IncidentListView(IncidentAccessMixin, ListView):
    model = Incident
    template_name = "incidents/incident_list.html"
    context_object_name = "incidents"
    extra_context = {"nav": "incidents"}

    def get_queryset(self):
        qs = Incident.objects.select_related("station").for_user(self.request.user)
        status = self.request.GET.get("status")
        if status in ("open", "review", "closed"):
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status"] = self.request.GET.get("status", "")
        return ctx


class IncidentFormMixin(IncidentAccessMixin):
    model = Incident
    form_class = IncidentForm
    template_name = "incidents/incident_form.html"

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["user"] = self.request.user
        return kw


class IncidentCreateView(IncidentFormMixin, CreateView):
    extra_context = {"nav": "incidents", "mode": "add"}

    def form_valid(self, form):
        form.instance.logged_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("incidents:detail", args=[self.object.pk])


class IncidentUpdateView(IncidentFormMixin, UpdateView):
    context_object_name = "incident"
    extra_context = {"nav": "incidents", "mode": "edit"}

    def get_queryset(self):
        return Incident.objects.for_user(self.request.user)

    def get_success_url(self):
        return reverse_lazy("incidents:detail", args=[self.object.pk])


class IncidentDetailView(IncidentAccessMixin, DetailView):
    model = Incident
    template_name = "incidents/incident_detail.html"
    context_object_name = "incident"
    extra_context = {"nav": "incidents"}

    def get_queryset(self):
        return Incident.objects.select_related("station").for_user(self.request.user)


class IncidentDeleteView(IncidentAccessMixin, DeleteView):
    model = Incident
    template_name = "incidents/incident_confirm_delete.html"
    context_object_name = "incident"
    extra_context = {"nav": "incidents"}
    success_url = reverse_lazy("incidents:list")

    def get_queryset(self):
        return Incident.objects.for_user(self.request.user)
