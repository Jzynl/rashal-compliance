from django.db import models


class ScopedQuerySet(models.QuerySet):
    """
    Base for every queryset that must respect station scope.

    Subclasses implement _scope_filter(station_ids).
    """

    def for_user(self, user):
        if user is None or not user.is_authenticated:
            return self.none()
        station_ids = user.accessible_station_ids()
        if station_ids is None:
            return self
        if not station_ids:
            return self.none()
        return self._scope_filter(station_ids)

    def _scope_filter(self, station_ids):
        raise NotImplementedError
