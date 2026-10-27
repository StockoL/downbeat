import json
import re

import pytest
from django.contrib.staticfiles import finders

pytestmark = pytest.mark.django_db


def test_manifest_is_public_and_installable(anon_client, teacher):
    response = anon_client.get("/manifest.webmanifest")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/manifest+json")
    manifest = json.loads(response.content)
    assert manifest["display"] == "standalone" and manifest["start_url"] == "/"
    assert {icon["sizes"] for icon in manifest["icons"]} == {"192x192", "512x512"}
    assert any(icon.get("purpose") == "maskable" for icon in manifest["icons"])
    for icon in manifest["icons"]:
        assert finders.find(icon["src"].removeprefix("/static/")), icon["src"]


def test_service_worker_is_public_and_versioned(anon_client, teacher):
    response = anon_client.get("/sw.js")
    assert response.status_code == 200
    assert response["Content-Type"] == "application/javascript"
    assert response["Service-Worker-Allowed"] == "/"
    assert response["Cache-Control"] == "no-cache"
    source = response.content.decode()
    assert "__CACHE_VERSION__" not in source and "/*__PRECACHE__*/" not in source
    assert re.search(r'const VERSION = "[0-9a-f]{12}"', source)


def test_every_precached_file_exists(anon_client, teacher):
    source = anon_client.get("/sw.js").content.decode()
    precache = json.loads(re.search(r"const PRECACHE = (\[.*?\]);", source).group(1))
    assert "/offline/" in precache
    for url in precache:
        if url.startswith("/static/"):
            assert finders.find(url.removeprefix("/static/")), url
        else:
            assert anon_client.get(url).status_code == 200, url


def test_offline_page_is_public_and_holds_no_pupil_data(anon_client, teacher, timetable, pupils):
    html = anon_client.get("/offline/").content.decode()
    assert "Not reachable" in html
    assert not any(str(p) in html for p in pupils)


def test_pages_link_the_manifest_icon_and_worker(client, timetable):
    html = client.get("/settings/").content.decode()
    assert 'rel="manifest"' in html
    assert "apple-touch-icon" in html and "icons/icon-180.png" in html
    assert "js/queue.js" in html


def test_sign_out_form_is_marked_to_clear_saved_pages(client, timetable):
    assert "data-sign-out" in client.get("/settings/").content.decode()
