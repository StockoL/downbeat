"""
The installable app: manifest, service worker and the offline fallback. All three are public,
since a browser fetches them before anyone signs in; none of them carries pupil data.
"""

import hashlib
import json
from functools import cache

from django.contrib.staticfiles import finders
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.views.decorators.http import require_GET
from django_looseleaf import tokens

# The app shell: everything a page needs besides its own HTML.
SHELL = [
    "css/downbeat.css",
    "looseleaf/looseleaf.css",
    "looseleaf/looseleaf.js",
    "theme/looseleaf-tokens.css",
    "js/htmx.min.js",
    "js/canvas.js",
    "js/queue.js",
    "icons/icon-180.png",
    "icons/icon-192.png",
]


@cache
def _worker_source():
    """queue.js with its cache version and precache list filled in. The version changes whenever
    any shell file changes, so the iPad drops stale copies the next time it is online."""
    digest = hashlib.sha256()
    for path in SHELL:
        digest.update(path.encode())
        with open(finders.find(path), "rb") as f:
            digest.update(f.read())
    with open(finders.find("js/queue.js"), encoding="utf-8") as f:
        source = f.read()
    precache = [static(path) for path in SHELL] + ["/offline/"]
    return (
        source.replace("__CACHE_VERSION__", digest.hexdigest()[:12])
        .replace("/*__PRECACHE__*/[]", json.dumps(precache))
    )


@require_GET
def service_worker(request):
    response = HttpResponse(_worker_source(), content_type="application/javascript")
    response["Cache-Control"] = "no-cache"  # always check for a new worker
    response["Service-Worker-Allowed"] = "/"
    return response


@require_GET
def manifest(request):
    return JsonResponse({
        "name": "Downbeat",
        "short_name": "Downbeat",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": tokens.get("color.surface", scheme="light"),
        "theme_color": tokens.get("color.surface", scheme="light"),
        "icons": [
            {"src": static("icons/icon-192.png"), "sizes": "192x192", "type": "image/png"},
            {"src": static("icons/icon-512.png"), "sizes": "512x512", "type": "image/png"},
            {"src": static("icons/maskable-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }, content_type="application/manifest+json")


@require_GET
def offline(request):
    return render(request, "core/offline.html")
