from django import forms

from payroll.models import (PayLine, PayRun, RetrenchmentBatch, RetrenchmentPayment)


class PayRunForm(forms.ModelForm):
    class Meta:
        model = PayRun
        fields = ["year", "month", "reference", "narration", "note"]
        widgets = {
            "reference": forms.TextInput(attrs={"placeholder": "Auto from month, e.g. OCT"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["reference"].required = False
        self.fields["narration"].required = False
        self.fields["note"].required = False


class PayLineForm(forms.ModelForm):
    class Meta:
        model = PayLine
        fields = ["beneficiary_name", "beneficiary_account", "amount", "narration", "include"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["beneficiary_account"].required = False
        self.fields["narration"].required = False


class RetrenchmentBatchForm(forms.ModelForm):
    class Meta:
        model = RetrenchmentBatch
        fields = ["station", "year", "title", "description", "note"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["station"].required = False
        self.fields["note"].required = False


class RetrenchmentPaymentForm(forms.ModelForm):
    class Meta:
        model = RetrenchmentPayment
        fields = ["name", "account_no", "amount", "bank", "branch", "description", "include"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for n in ("account_no", "bank", "branch", "description"):
            self.fields[n].required = False
