from django import forms

from audit.models import Audit, AuditFinding


class _DateInput(forms.DateInput):
    input_type = "date"


class AuditForm(forms.ModelForm):
    class Meta:
        model = Audit
        fields = ["station", "template", "title", "audit_date", "auditor_name", "status", "summary"]
        widgets = {
            "audit_date": _DateInput(),
            "summary": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("template", "audit_date", "auditor_name", "summary"):
            self.fields[name].required = False
        from audit.models import ChecklistTemplate
        self.fields["template"].queryset = ChecklistTemplate.objects.filter(is_active=True)
        self.fields["template"].empty_label = "— No checklist (free-form) —"


class AuditFindingForm(forms.ModelForm):
    class Meta:
        model = AuditFinding
        fields = ["description", "category", "status", "responsible", "due_date", "resolution_note"]
        widgets = {
            "due_date": _DateInput(),
            "description": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("category", "responsible", "due_date", "resolution_note"):
            self.fields[name].required = False
