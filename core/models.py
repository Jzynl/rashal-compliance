from django.db import models


class TimeStampedModel(models.Model):
    """created_at / updated_at on everything. No exceptions."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
