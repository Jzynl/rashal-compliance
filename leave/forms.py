from django import forms

from leave.models import LeaveBalance, LeaveType


class LeaveTypeForm(forms.ModelForm):
    class Meta:
        model = LeaveType
        fields = ["name", "is_paid", "annual_entitlement_days", "is_active", "note"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["annual_entitlement_days"].required = False
        self.fields["note"].required = False


class LeaveBalanceForm(forms.ModelForm):
    class Meta:
        model = LeaveBalance
        fields = ["employee", "leave_type", "year", "allowed",
                  "taken_first", "taken_second", "status", "note"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["note"].required = False
        self.fields["status"].required = False
        self.fields["employee"].queryset = self.fields["employee"].queryset.filter(is_active=True)
        self.fields["leave_type"].queryset = LeaveType.objects.filter(is_active=True)
        # Prefill the allowance from the chosen type when adding a new balance.
        if not self.instance.pk:
            self.fields["allowed"].required = False
