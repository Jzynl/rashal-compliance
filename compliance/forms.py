"""
Front-end document upload.

The Django admin can attach files, but it is not something you hand a
station manager. This form is: pick a type, choose a file, done. It
validates extension and size here so a bad upload is rejected at the door
rather than after it hits disk.
"""

import os

from django import forms
from django.conf import settings

from compliance.models import ComplianceDocument, ComplianceType
from stations.models import Station


def validate_upload(f):
    """
    Shared file check: extension, size, not empty. Same rules the single
    upload form enforces, so both entry points reject a bad file at the
    door rather than after it hits disk.
    """
    ext = os.path.splitext(f.name)[1].lower()
    allowed = settings.ALLOWED_UPLOAD_EXTENSIONS
    if ext not in allowed:
        raise forms.ValidationError(
            f"That file type isn't allowed. Upload one of: {', '.join(allowed)}."
        )
    if f.size > settings.MAX_UPLOAD_BYTES:
        mb = settings.MAX_UPLOAD_BYTES / (1024 * 1024)
        raise forms.ValidationError(f"That file is too big. The limit is {mb:.0f} MB.")
    if f.size == 0:
        raise forms.ValidationError("That file is empty.")
    return f


class DocumentUploadForm(forms.Form):
    doc_type = forms.ChoiceField(
        choices=ComplianceDocument.DocType.choices,
        label="What is this?",
    )
    file = forms.FileField(
        label="Certificate or receipt (PDF or image)",
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf,.jpg,.jpeg,.png"}),
    )

    def clean_file(self):
        return validate_upload(self.cleaned_data["file"])


class AddComplianceForm(forms.Form):
    """
    One page to record a compliance certificate -- a brand-new obligation
    or a renewal of an existing one. Building the period and superseding
    any previous one is left to services.activate_period; this form only
    gathers and validates input.
    """

    station = forms.ModelChoiceField(
        queryset=Station.objects.none(),
        label="Station",
    )
    compliance_type = forms.ModelChoiceField(
        queryset=ComplianceType.objects.active(),
        label="Compliance type",
    )
    label = forms.CharField(
        required=False,
        label="Label",
        help_text="Only if this station holds more than one of this type.",
        widget=forms.TextInput(attrs={"placeholder": "e.g. Diesel line"}),
    )

    certificate_number = forms.CharField(
        required=False,
        label="Certificate / licence number",
        widget=forms.TextInput(attrs={"placeholder": "e.g. PRL-2024-123"}),
    )
    start_date = forms.DateField(
        label="Start date",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    expiry_date = forms.DateField(
        label="Expiry date",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    amount_paid = forms.DecimalField(
        required=False, min_value=0, max_digits=14, decimal_places=2,
        label="Amount paid (TZS)",
        widget=forms.NumberInput(attrs={"placeholder": "TZS"}),
    )
    payment_reference = forms.CharField(
        required=False,
        label="Payment reference",
        widget=forms.TextInput(attrs={"placeholder": "Control / receipt no."}),
    )

    certificate_file = forms.FileField(
        required=False,
        label="Certificate file",
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf,.jpg,.jpeg,.png"}),
    )
    receipt_file = forms.FileField(
        required=False,
        label="Receipt file",
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf,.jpg,.jpeg,.png"}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Scope the station dropdown to what this user may write to.
        if user is not None:
            self.fields["station"].queryset = Station.objects.for_user(user).active()
        else:
            self.fields["station"].queryset = Station.objects.active()

    def clean_certificate_file(self):
        f = self.cleaned_data.get("certificate_file")
        return validate_upload(f) if f else f

    def clean_receipt_file(self):
        f = self.cleaned_data.get("receipt_file")
        return validate_upload(f) if f else f

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        expiry = cleaned.get("expiry_date")
        if start and expiry and expiry < start:
            self.add_error("expiry_date", "Expiry date cannot be before the start date.")
        return cleaned


class ComplianceTypeForm(forms.ModelForm):
    """
    Add or edit a compliance category from the front end. Rare, high-impact
    (a new type becomes a column in the matrix and a card for every station),
    so it stays behind the officer/admin roles in the view.
    """

    # alert_thresholds is a JSON list on the model, but people think in
    # "365, 180, 90, 30, 7, 0" -- take it as text and convert.
    alert_thresholds_text = forms.CharField(
        label="Alert rungs (days before expiry)",
        help_text="Comma-separated days that trigger an alert, e.g. "
                  "365, 180, 90, 30, 7, 0",
        widget=forms.TextInput(attrs={"placeholder": "365, 180, 90, 30, 7, 0"}),
    )

    class Meta:
        model = ComplianceType
        fields = [
            "name", "short_code", "issuing_authority", "description",
            "default_validity_months", "requires_payment_receipt",
            "is_perpetual", "sort_order", "is_active",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pre-fill the text box from the stored list when editing.
        if self.instance and self.instance.pk:
            self.fields["alert_thresholds_text"].initial = ", ".join(
                str(n) for n in self.instance.alert_thresholds
            )
        else:
            self.fields["alert_thresholds_text"].initial = "365, 180, 90, 30, 7, 0"

    def clean_short_code(self):
        # Codes are shown large and used in URLs/columns -- keep them tidy.
        return self.cleaned_data["short_code"].strip().upper()

    def clean_alert_thresholds_text(self):
        raw = self.cleaned_data["alert_thresholds_text"]
        parts = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
        try:
            days = sorted({int(p) for p in parts}, reverse=True)
        except ValueError:
            raise forms.ValidationError(
                "Use whole numbers separated by commas, e.g. 365, 180, 90, 30, 7, 0."
            )
        if any(d < 0 for d in days):
            raise forms.ValidationError("Days cannot be negative.")
        if not days:
            raise forms.ValidationError("Enter at least one alert rung.")
        return days

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.alert_thresholds = self.cleaned_data["alert_thresholds_text"]
        if commit:
            obj.save()
        return obj