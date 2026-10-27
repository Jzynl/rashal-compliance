"""Mirror of stations.signals: a new type fills in every station."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from compliance.models import ComplianceType, StationCompliance


@receiver(post_save, sender=ComplianceType, dispatch_uid="provision_type_across_stations")
def provision_type_across_stations(sender, instance, created, **kwargs):
    if not created or not instance.is_active:
        return
    from stations.models import Station

    StationCompliance.objects.bulk_create(
        [
            StationCompliance(station=station, compliance_type=instance)
            for station in Station.objects.filter(is_active=True)
        ],
        ignore_conflicts=True,
    )
