from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.urls import reverse

from timetable.models import Timetable

# Reachable without signing in: the login page itself and what a browser fetches before it.
PUBLIC_PATHS = ("/login/", "/manifest.webmanifest", "/sw.js", "/offline/")


class GateMiddleware:
    """
    Three gates, in order. No account yet: the first-run setup, which creates one.
    Signed out: the login page. Signed in but no timetable: the setup again.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if path.startswith("/" + settings.STATIC_URL.lstrip("/")) or path.startswith(PUBLIC_PATHS):
            return self.get_response(request)

        setup_url = reverse("setup")
        if not get_user_model().objects.exists():
            return self.get_response(request) if path == setup_url else redirect(setup_url)
        if not request.user.is_authenticated:
            if path == reverse("sync") or path.endswith("/state/"):
                # The device's queue reads this as "keep everything and ask to sign in".
                return JsonResponse({"error": "signed out"}, status=401)
            login_url = f"{reverse('login')}?{urlencode({'next': request.get_full_path()})}"
            if request.headers.get("HX-Request"):
                # A sheet's request must move the whole page, not load the login form into the sheet.
                response = HttpResponse(status=204)
                response["HX-Redirect"] = login_url
                return response
            return redirect(login_url)
        if path != setup_url and not Timetable.objects.exists():
            return redirect(setup_url)
        return self.get_response(request)


class BadInputMiddleware:
    """
    A malformed id or value that reaches a model lookup raises ValidationError. Forms catch their
    own, so one escaping a view is bad input, not a fault: answer 400 with a plain page, not 500.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if isinstance(exception, ValidationError):
            return HttpResponseBadRequest(render_to_string("400.html"))
        return None


class PendingMigrationsMiddleware:
    """
    A database behind the code (started with runserver, or after an update, without migrating) fails
    on every page with a server error that leads nowhere. Until the migrations are in, show what to
    run instead. Checked on each request until it passes once, then never again for this process.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.up_to_date = False

    def __call__(self, request):
        if not self.up_to_date:
            if self.pending():
                return HttpResponse(render_to_string("errors/migrations.html"), status=503)
            self.up_to_date = True
        return self.get_response(request)

    @staticmethod
    def pending():
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        executor = MigrationExecutor(connection)
        return bool(executor.migration_plan(executor.loader.graph.leaf_nodes()))
