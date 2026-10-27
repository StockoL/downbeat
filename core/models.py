import uuid

from django.db import models


class Base(models.Model):
    """UUID key and timestamps on every table, so offline rows merge without renumbering."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
