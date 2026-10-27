import json
import mimetypes
import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from compliance.forms import AddComplianceForm, DocumentUploadForm
from compliance.models import (
    ComplianceDocument, CompliancePeriod, ComplianceType, StationCompliance,
)
from compliance.services import activate_period, attach_document
from core import bands
from core.mixins import RoleRequiredMixin
from core.roles import GLOBAL_SCOPE_ROLES


def band_summary(obligations):
    """Count obligations per band. Used by cards and KPI strips."""
    counts = {b.key: 0 for b in bands.ALL_BANDS}
    for sc in obligations:
        counts[sc.band.key] += 1
    return counts


class TypeListView(LoginRequiredMixin, ListView):
    """The compliance card grid. One card per type."""

    template_name = "compliance/type_list.html"
    extra_context = {"nav": "compliance"}
    context_object_name = "cards"

    def get_queryset(self):
        # Scope is applied to obligations, not to types: everyone sees the
        # same 14 types, but the counts on each card are their own.
        return StationCompliance.objects.for_user(self.request.user).live().with_related()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obligations = list(self.object_list)

        cards = []
        for ctype in ComplianceType.objects.active():
            mine = [sc for sc in obligations if sc.compliance_type_id == ctype.pk]
            if not mine:
                continue
            counts = band_summary(mine)
            worst = min((sc.band for sc in mine), key=lambda b: b.rank)
            cards.append({
                "type": ctype,
                "obligations": mine,
                "counts": counts,
                "worst": worst,
                "station_count": len(mine),
                "needs_attention": sum(
                    counts[k] for k in ("expired", "critical", "warning")
                ),
            })

        # Worst first. The thing on fire is top-left, always.
        cards.sort(key=lambda c: (c["worst"].rank, c["type"].sort_order))
        ctx["cards"] = cards
        return ctx


class TypeDetailView(LoginRequiredMixin, DetailView):
    """Click EWURA -> every station's EWURA."""

    model = ComplianceType
    template_name = "compliance/type_detail.html"
    context_object_name = "ctype"
    extra_context = {"nav": "compliance"}

    def get_queryset(self):
        # Types themselves are not station-scoped: everyone sees the same
        # 14. The scoping happens on the obligations in get_context_data.
        return ComplianceType.objects.active()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        rows = list(
            StationCompliance.objects.for_user(self.request.user)
            .live()
            .filter(compliance_type=self.object)
            .with_related()
        )
        # Sorted by urgency, not by insertion order. The grid is a work
        # queue, not a record.
        rows.sort(key=lambda sc: (sc.band.rank, sc.days_left or 99999))
        ctx["rows"] = rows
        ctx["counts"] = band_summary(rows)
        return ctx


class MatrixView(RoleRequiredMixin, ListView):
    """Stations x types. Super admin and officers only."""

    allowed_roles = GLOBAL_SCOPE_ROLES
    template_name = "compliance/matrix.html"
    extra_context = {"nav": "matrix"}
    context_object_name = "obligations"

    def get_queryset(self):
        return (
            StationCompliance.objects.for_user(self.request.user)
            .live().with_related()
        )

    def get_context_data(self, **kwargs):
        from stations.models import Station

        ctx = super().get_context_data(**kwargs)
        obligations = list(self.object_list)
        lookup = {(sc.station_id, sc.compliance_type_id): sc for sc in obligations}

        types = list(ComplianceType.objects.active())
        stations = list(Station.objects.for_user(self.request.user).active())

        ctx["types"] = types
        ctx["grid"] = [
            {"station": s, "cells": [lookup.get((s.pk, t.pk)) for t in types]}
            for s in stations
        ]
        return ctx


class ObligationDetailView(LoginRequiredMixin, DetailView):
    """
    Current certificate on top, history below.

    95% of visits ask 'is this valid right now, and where is the
    certificate' -- that gets zero clicks. History gets one.
    """

    model = StationCompliance
    template_name = "compliance/obligation_detail.html"
    context_object_name = "obligation"
    extra_context = {"nav": "compliance"}

    def get_queryset(self):
        # for_user() goes INSIDE the lookup. Defining get_queryset() on the
        # class replaces ScopedQuerysetMixin's version rather than extending
        # it -- so the scope has to be applied right here or a manager reads
        # another station's certificates. This exact override leaked once.
        return StationCompliance.objects.for_user(self.request.user).with_related()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        sc = self.object
        ctx["current"] = sc.current_period
        ctx["processing"] = sc.periods.filter(status="processing").first()
        ctx["lapsed_behind_renewal"] = sc.lapsed_period
        ctx["history"] = (
            sc.periods.exclude(pk=sc.current_period_id)
            .prefetch_related("documents")
            .order_by("-start_date", "-created_at")
        )
        ctx["can_write"] = self.request.user.can_write
        return ctx


class AddComplianceView(LoginRequiredMixin, View):
    """
    Front-end replacement for adding a compliance period through the
    Django admin. Records a new certificate -- new obligation or renewal --
    on one page, files included. All the period-swap logic stays in
    services.activate_period.
    """

    template_name = "compliance/add_compliance.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.can_write:
            raise PermissionDenied("Your role can view compliance but not add it.")
        return super().dispatch(request, *args, **kwargs)

    def _validity_map(self):
        # short_code pk -> months, so the page can suggest an expiry date.
        # Perpetual types map to 0 (no suggestion).
        m = {
            str(t.pk): (0 if t.is_perpetual else t.default_validity_months)
            for t in ComplianceType.objects.active()
        }
        return json.dumps(m)

    def get(self, request):
        return render(request, self.template_name, {
            "form": AddComplianceForm(user=request.user),
            "nav": "compliance",
            "type_validity": self._validity_map(),
        })

    def post(self, request):
        form = AddComplianceForm(request.POST, request.FILES, user=request.user)
        if not form.is_valid():
            return render(request, self.template_name, {
                "form": form,
                "nav": "compliance",
                "type_validity": self._validity_map(),
            })

        d = form.cleaned_data

        # Get or create the obligation (the permanent "station holds type").
        sc, _ = StationCompliance.objects.get_or_create(
            station=d["station"],
            compliance_type=d["compliance_type"],
            label=d["label"] or "",
        )

        # A fresh period every time. activate_period supersedes any previous
        # current period and moves the pointer, atomically.
        period = CompliancePeriod.objects.create(
            station_compliance=sc,
            status=CompliancePeriod.Status.PROCESSING,
            is_current=False,
            amount_paid=d.get("amount_paid"),
            payment_reference=d.get("payment_reference", ""),
            submitted_by=request.user,
        )

        try:
            activate_period(
                period,
                d["start_date"],
                d["expiry_date"],
                d.get("certificate_number", ""),
                user=request.user,
            )
        except ValidationError as exc:
            period.delete()
            for msg in exc.messages:
                form.add_error(None, msg)
            return render(request, self.template_name, {
                "form": form,
                "nav": "compliance",
                "type_validity": self._validity_map(),
            })

        # Attach files if provided.
        if d.get("certificate_file"):
            attach_document(period, d["certificate_file"],
                            ComplianceDocument.DocType.CERTIFICATE, user=request.user)
        if d.get("receipt_file"):
            attach_document(period, d["receipt_file"],
                            ComplianceDocument.DocType.RECEIPT, user=request.user)

        messages.success(
            request,
            f"Recorded {sc.compliance_type.short_code} for {sc.station.name}, "
            f"valid until {d['expiry_date']:%d %b %Y}."
        )
        return redirect(sc.get_absolute_url())


class UploadDocumentView(LoginRequiredMixin, View):
    """
    Attach a certificate or receipt to a period from the front end.

    Scope is enforced by resolving the period through for_user(): a manager
    can only upload to a station they hold. Write permission is checked too --
    an auditor can look but not add.
    """

    template_name = "compliance/upload.html"

    def _get_period(self, request, period_pk):
        return get_object_or_404(
            CompliancePeriod.objects.for_user(request.user).with_related(),
            pk=period_pk,
        )

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.can_write:
            raise PermissionDenied("Your role can view documents but not upload them.")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, period_pk):
        period = self._get_period(request, period_pk)
        # Pre-select the type that's missing, so the common case is one tap.
        initial = {}
        if not period.receipt and period.station_compliance.compliance_type.requires_payment_receipt:
            initial["doc_type"] = ComplianceDocument.DocType.RECEIPT
        elif not period.certificate:
            initial["doc_type"] = ComplianceDocument.DocType.CERTIFICATE
        return render(request, self.template_name, {
            "period": period,
            "obligation": period.station_compliance,
            "form": DocumentUploadForm(initial=initial),
            "nav": "compliance",
        })

    def post(self, request, period_pk):
        period = self._get_period(request, period_pk)
        form = DocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            doc = attach_document(
                period,
                form.cleaned_data["file"],
                form.cleaned_data["doc_type"],
                user=request.user,
            )
            messages.success(
                request,
                f"{doc.get_doc_type_display()} uploaded for "
                f"{period.station_compliance.station.name} · "
                f"{period.station_compliance.compliance_type.short_code}.",
            )
            return redirect(period.station_compliance.get_absolute_url())
        return render(request, self.template_name, {
            "period": period,
            "obligation": period.station_compliance,
            "form": form,
            "nav": "compliance",
        })


def serve_document(request, pk):
    """
    The ONLY way a compliance document leaves the server.

    for_user() is inside the lookup, not an if-check afterwards. A manager
    typing another station's document id gets a 404, not a certificate.
    """
    if not request.user.is_authenticated:
        raise Http404

    doc = get_object_or_404(
        ComplianceDocument.objects.for_user(request.user).select_related(
            "period__station_compliance__station"
        ),
        pk=pk,
    )

    path = doc.file.path
    if not os.path.exists(path):
        raise Http404("File missing from storage.")

    content_type = doc.content_type or mimetypes.guess_type(path)[0] \
        or "application/octet-stream"

    # ?download=1 forces a save; without it, PDFs open inline in the modal.
    as_attachment = request.GET.get("download") == "1"

    response = FileResponse(
        open(path, "rb"),
        content_type=content_type,
        as_attachment=as_attachment,
        filename=doc.original_name or os.path.basename(path),
    )
    response["X-Content-Type-Options"] = "nosniff"
    # Allow this file to load inside the in-app viewer's iframe. The global
    # X-Frame-Options is DENY (clickjacking protection); SAMEORIGIN here lets
    # our own page frame the document while still blocking other sites.
    response["X-Frame-Options"] = "SAMEORIGIN"
    return response