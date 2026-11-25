from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import (CreateView, DeleteView, DetailView, ListView, UpdateView, View)

from audit.forms import AuditFindingForm, AuditForm
from audit.models import Audit, AuditFinding, AuditResponse, ChecklistItem
from core import roles
from core.mixins import RoleRequiredMixin

AUDIT_ROLES = {roles.SUPER_ADMIN, roles.AUDITOR, roles.COMPLIANCE_OFFICER}


class AuditAccessMixin(RoleRequiredMixin):
    allowed_roles = AUDIT_ROLES


# --- Audits ---------------------------------------------------------------
class AuditListView(AuditAccessMixin, ListView):
    model = Audit
    template_name = "audit/audit_list.html"
    context_object_name = "audits"
    extra_context = {"nav": "audit"}

    def get_queryset(self):
        return Audit.objects.select_related("station").all()


class AuditCreateView(AuditAccessMixin, CreateView):
    model = Audit
    form_class = AuditForm
    template_name = "audit/audit_form.html"
    extra_context = {"nav": "audit", "mode": "add"}

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("audit:audit_detail", args=[self.object.pk])


class AuditUpdateView(AuditAccessMixin, UpdateView):
    model = Audit
    form_class = AuditForm
    template_name = "audit/audit_form.html"
    context_object_name = "audit"
    extra_context = {"nav": "audit", "mode": "edit"}

    def get_success_url(self):
        return reverse("audit:audit_detail", args=[self.object.pk])


class AuditDetailView(AuditAccessMixin, DetailView):
    model = Audit
    template_name = "audit/audit_detail.html"
    context_object_name = "audit"
    extra_context = {"nav": "audit"}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        audit = self.object
        ctx["findings"] = audit.findings.all()

        checklist = []
        if audit.template_id:
            responses = {r.item_id: r for r in audit.responses.all()}
            for section in audit.template.sections.prefetch_related("items").all():
                rows = []
                for item in section.items.all():
                    r = responses.get(item.id)
                    rows.append({
                        "item": item,
                        "answer": r.answer if r else "",
                        "comment": r.comment if r else "",
                    })
                checklist.append({"section": section, "rows": rows})
        ctx["checklist"] = checklist
        ctx["item_total"] = audit.template.item_count if audit.template_id else 0
        return ctx


class ChecklistSaveView(AuditAccessMixin, View):
    """Save every checklist answer + comment for an audit in one post."""

    def post(self, request, pk):
        audit = get_object_or_404(Audit, pk=pk)
        if not audit.template_id:
            messages.error(request, "This audit has no checklist.")
            return redirect("audit:audit_detail", pk=audit.pk)

        valid = {c[0] for c in AuditResponse.Answer.choices}
        items = ChecklistItem.objects.filter(section__template=audit.template)
        for item in items:
            answer = request.POST.get(f"answer_{item.id}", "")
            if answer not in valid:
                answer = ""
            comment = request.POST.get(f"comment_{item.id}", "").strip()[:255]
            AuditResponse.objects.update_or_create(
                audit=audit, item=item,
                defaults={"answer": answer, "comment": comment},
            )
        messages.success(request, "Checklist saved.")
        return redirect("audit:audit_detail", pk=audit.pk)


class AuditDeleteView(AuditAccessMixin, DeleteView):
    model = Audit
    template_name = "audit/audit_confirm_delete.html"
    context_object_name = "audit"
    extra_context = {"nav": "audit"}
    success_url = reverse_lazy("audit:audit_list")


# --- Findings -------------------------------------------------------------
class FindingCreateView(AuditAccessMixin, CreateView):
    model = AuditFinding
    form_class = AuditFindingForm
    template_name = "audit/finding_form.html"
    extra_context = {"nav": "audit", "mode": "add"}

    def dispatch(self, request, *args, **kwargs):
        self.audit = get_object_or_404(Audit, pk=kwargs["audit_pk"])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.audit = self.audit
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["audit"] = self.audit
        return ctx

    def get_success_url(self):
        return reverse("audit:audit_detail", args=[self.audit.pk])


class FindingUpdateView(AuditAccessMixin, UpdateView):
    model = AuditFinding
    form_class = AuditFindingForm
    template_name = "audit/finding_form.html"
    context_object_name = "finding"
    extra_context = {"nav": "audit", "mode": "edit"}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["audit"] = self.object.audit
        return ctx

    def get_success_url(self):
        return reverse("audit:audit_detail", args=[self.object.audit.pk])


class FindingDeleteView(AuditAccessMixin, DeleteView):
    model = AuditFinding
    template_name = "audit/finding_confirm_delete.html"
    context_object_name = "finding"
    extra_context = {"nav": "audit"}

    def get_success_url(self):
        return reverse("audit:audit_detail", args=[self.object.audit.pk])
