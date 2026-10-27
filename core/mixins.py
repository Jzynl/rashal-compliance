"""
View mixins that make the safe path the only path.

Django has no global query scope. The rule for this project:
never touch Model.objects directly in a view. Always go through
get_queryset() on one of these mixins, which applies for_user().
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from core import roles


class RoleRequiredMixin(LoginRequiredMixin):
    """Restrict a view to a set of role names."""

    allowed_roles: set | None = None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        if self.allowed_roles and not request.user.has_any_role(self.allowed_roles):
            raise PermissionDenied("Your role does not have access to this page.")
        return super().dispatch(request, *args, **kwargs)


class ScopedQuerysetMixin(LoginRequiredMixin):
    """
    Applies .for_user(request.user) to the view's queryset.

    The model manager must expose for_user(). Every compliance-related
    model in this project does.
    """

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.for_user(self.request.user)


class WriteAccessMixin(RoleRequiredMixin):
    allowed_roles = roles.WRITE_ROLES


class SuperAdminOnlyMixin(RoleRequiredMixin):
    allowed_roles = {roles.SUPER_ADMIN}
