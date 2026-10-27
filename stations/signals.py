"""
Auto-provisioning.

A new station must immediately own one StationCompliance per active
compliance type, and a new compliance type must appear on every active
station. Otherwise the grid grows holes and nobody notices.

This lives in a signal rather than a service because the Django admin
saves models directly -- no view of ours runs -- and Setup is done in
the admin.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from stations.models import Station


@receiver(post_save, sender=Station, dispatch_uid="provision_station_compliances")
def provision_station_compliances(sender, instance, created, **kwargs):
    if not created:
        return
    from compliance.models import ComplianceType, StationCompliance

    StationCompliance.objects.bulk_create(
        [
            StationCompliance(station=instance, compliance_type=ctype)
            for ctype in ComplianceType.objects.filter(is_active=True)
        ],
        ignore_conflicts=True,
    )
