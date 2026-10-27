from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from compliance.models import StationCompliance
from compliance.views import band_summary
from stations.models import Station


class HomeView(LoginRequiredMixin, TemplateView):
    """
    One view, two shapes.

    A super admin asks "where are the problems across the network" and gets
    breadth: counts, then what needs action. A station manager asks "what
    must I do today" and gets a task list. Same queryset, same components,
    different landing page.
    """

    def get_template_names(self):
        if self.request.user.sees_all_stations:
            return ["dashboard/admin_home.html"]
        return ["dashboard/manager_home.html"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["nav"] = "home"
        user = self.request.user

        obligations = list(
            StationCompliance.objects.for_user(user).live().with_related()
        )
        # Worst first, always. The thing on fire is at the top.
        obligations.sort(key=lambda sc: (sc.band.rank, sc.days_left or 99999))

        stations = list(
            Station.objects.for_user(user).active().prefetch_related(
                "compliances__current_period",
                "compliances__compliance_type",
            )
        )

        ctx["counts"] = band_summary(obligations)
        ctx["obligations"] = obligations
        ctx["stations"] = stations
        ctx["attention"] = [
            sc for sc in obligations
            if sc.band.key in ("expired", "critical", "warning", "processing")
        ][:8]

        if not user.sees_all_stations:
            ctx["station"] = stations[0] if len(stations) == 1 else None

        return ctx