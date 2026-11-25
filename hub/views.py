from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from core.modules import visible_modules


class HubView(LoginRequiredMixin, TemplateView):
    """The landing page after login: a role-aware tile launcher."""

    template_name = "hub/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["modules"] = visible_modules(self.request.user)
        return ctx
