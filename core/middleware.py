from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

from timetable.models import Timetable


class FirstRunMiddleware:
    """Until a timetable exists, every page leads to the setup screen."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        setup_url = reverse("setup")
        exempt = request.path.startswith((setup_url, "/" + settings.STATIC_URL.lstrip("/")))
        if not exempt and not Timetable.objects.exists():
            return redirect(setup_url)
        return self.get_response(request)
