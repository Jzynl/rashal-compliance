from django.db import models
from django.urls import reverse

from accounts.managers import ScopedQuerySet
from core.models import TimeStampedModel


class StationQuerySet(ScopedQuerySet):
    def _scope_filter(self, station_ids):
        return self.filter(id__in=station_ids)

    def active(self):
        return self.filter(is_active=True)


class Station(TimeStampedModel):
    """A physical petrol station."""

    class Region(models.TextChoices):
        DAR = "dar_es_salaam", "Dar es Salaam"
        ARUSHA = "arusha", "Arusha"
        DODOMA = "dodoma", "Dodoma"
        MWANZA = "mwanza", "Mwanza"
        MOROGORO = "morogoro", "Morogoro"
        MBEYA = "mbeya", "Mbeya"
        MTWARA = "mtwara", "Mtwara"
        LINDI = "lindi", "Lindi"
        TANGA = "tanga", "Tanga"
        SINGIDA = "singida", "Singida"
        MANYARA = "manyara", "Manyara"
        RUVUMA = "ruvuma", "Ruvuma"
        PWANI = "pwani", "Pwani"
        IRINGA = "iringa", "Iringa"
        KILIMANJARO = "kilimanjaro", "Kilimanjaro"
        OTHER = "other", "Other"

    name = models.CharField(max_length=120)
    code = models.CharField(
        max_length=20, unique=True,
        help_text="Short internal reference, e.g. TZ-KRK-04",
    )
    region = models.CharField(max_length=32, choices=Region.choices)
    district = models.CharField(max_length=80, blank=True)
    address = models.TextField(blank=True)

    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Inactive stations generate no alerts and are hidden from the map.",
    )
    commissioned_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    objects = StationQuerySet.as_manager()

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["region"]),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("stations:detail", args=[self.pk])

    @property
    def has_coordinates(self):
        return self.latitude is not None and self.longitude is not None

    def _obligation_bands(self):
        return [sc.band for sc in self.compliances.select_related(
            "compliance_type", "current_period",
        )]

    def worst_band(self):
        """
        The most urgent band across all of this station's obligations.

        Careful with this one: with 14 obligations per station, "worst of
        14" is pessimistic by construction -- even a well-run station
        usually has *something* in the warning band, so a worst-of pin
        goes orange almost permanently and stops carrying information.

        Use map_band() for the pin. Use this for sorting a station list,
        where relative ranking is what matters.
        """
        from core.bands import SAFE

        bands = self._obligation_bands()
        if not bands:
            return SAFE
        return min(bands, key=lambda b: b.rank)

    def map_band(self):
        """
        The pin colour. Answers one question only: is this station legally
        operating right now?

        expired  -> anything lapsed. The station is trading unlicensed.
        critical -> nothing lapsed, but something needs action inside 90 days.
        safe     -> neither.

        Deliberately blind to the warning band. A pin is a five-pixel dot
        seen from across a room; it gets one bit of meaning, not five.
        The counts live in the popup.
        """
        from core.bands import CRITICAL, EXPIRED, SAFE

        keys = {b.key for b in self._obligation_bands()}
        if "expired" in keys:
            return EXPIRED
        if "critical" in keys:
            return CRITICAL
        return SAFE

    def band_counts(self):
        """Per-band tally for the station popup and the station card."""
        from collections import Counter
        return Counter(b.key for b in self._obligation_bands())

    @property
    def attention_count(self):
        counts = self.band_counts()
        return counts["expired"] + counts["critical"] + counts["warning"]