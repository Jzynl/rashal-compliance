from django import forms

from incidents.models import Incident


class IncidentForm(forms.ModelForm):
    class Meta:
        model = Incident
        fields = ["station", "occurred_on", "occurred_time", "category", "severity",
                  "title", "description", "reported_by", "action_taken", "status"]
        widgets = {
            "occurred_on": forms.DateInput(attrs={"type": "date"}),
            "occurred_time": forms.TimeInput(attrs={"type": "time"}),
            "description": forms.Textarea(attrs={"rows": 3}),
            "action_taken": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        for n in ("occurred_time", "description", "reported_by", "action_taken"):
            self.fields[n].required = False
        # A station manager can only file against their own station(s).
        if user is not None and not user.sees_all_stations:
            from stations.models import Station
            ids = user.accessible_station_ids() or []
            self.fields["station"].queryset = Station.objects.filter(id__in=ids)
