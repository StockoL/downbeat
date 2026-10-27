import uuid

from django.db import models

from core.models import Base


def test_base_is_abstract_with_uuid_and_timestamps():
    assert Base._meta.abstract
    pk = Base._meta.get_field("id")
    assert isinstance(pk, models.UUIDField) and pk.primary_key
    assert isinstance(pk.default(), uuid.UUID)
    assert Base._meta.get_field("created_at").auto_now_add
    assert Base._meta.get_field("updated_at").auto_now


def test_desk_layout_renders(client, timetable):
    response = client.get("/settings/")
    assert response.status_code == 200
    assert b"htmx.min.js" in response.content
    assert b"downbeat.css" in response.content
