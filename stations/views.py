from django.views.generic import DetailView, ListView

from core.mixins import ScopedQuerysetMixin
from stations.models import Station


class StationListView(ScopedQuerysetMixin, ListView):
    model = Station
    template_name = "stations/list.html"
    context_object_name = "stations"
    extra_context = {"nav": "stations"}

    def get_queryset(self):
        return super().get_queryset().active()


class StationDetailView(ScopedQuerysetMixin, DetailView):
    """One station -> its 14 obligations, sorted by urgency."""

    model = Station
    template_name = "stations/detail.html"
    context_object_name = "station"
    extra_context = {"nav": "stations"}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obligations = list(
            self.object.compliances.select_related(
                "compliance_type", "current_period",
            )
        )
        obligations.sort(key=lambda sc: (sc.band.rank, sc.days_left or 99999))
        ctx["obligations"] = obligations
        return ctx
