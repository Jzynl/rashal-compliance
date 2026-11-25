from django import forms

from foundation.models import Employee, EmployeeCredential


class _DateInput(forms.DateInput):
    input_type = "date"


class EmployeeForm(forms.ModelForm):
    """Add / edit an employee. HR-only, so every field is shown."""

    class Meta:
        model = Employee
        fields = [
            "organisation",
            "first_name", "middle_name", "last_name",
            "gender", "date_of_birth", "national_id", "phone",
            "station", "department", "position", "job_title",
            "employment_category", "date_joined", "date_left", "is_active",
            "user",
            "bank_name", "bank_branch", "bank_account_number",
            "nssf_number", "nhif_number", "wcf_number", "tin",
        ]
        widgets = {
            "date_of_birth": _DateInput(),
            "date_joined": _DateInput(),
            "date_left": _DateInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make the common "add" path quick: nothing is required at the DB
        # level except names, so only names are required on the form too.
        for name, field in self.fields.items():
            if name not in ("first_name", "last_name"):
                field.required = False


class EmployeeCredentialForm(forms.ModelForm):
    class Meta:
        model = EmployeeCredential
        fields = ["employee", "kind", "title", "provider", "reference",
                  "issue_date", "expiry_date", "note"]
        widgets = {
            "issue_date": forms.DateInput(attrs={"type": "date"}),
            "expiry_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for n in ("provider", "reference", "issue_date", "expiry_date", "note"):
            self.fields[n].required = False
        self.fields["employee"].queryset = self.fields["employee"].queryset.filter(is_active=True)
