"""Signing in. One teacher; the login is the only door once the app is reachable from the iPad."""

from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.core.cache import cache

MAX_FAILURES = 5
LOCKOUT_SECONDS = 300


def _key(request):
    return f"login-failures:{request.META.get('REMOTE_ADDR', '')}"


class LoginView(auth_views.LoginView):
    """Django's login, with a pause after five wrong passwords from the same address."""

    template_name = "core/login.html"
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        if cache.get(_key(request), 0) >= MAX_FAILURES:
            messages.error(request, "Too many wrong passwords. Wait five minutes and try again.")
            return self.get(request, *args, **kwargs)
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        key = _key(self.request)
        cache.set(key, cache.get(key, 0) + 1, LOCKOUT_SECONDS)
        return super().form_invalid(form)

    def form_valid(self, form):
        cache.delete(_key(self.request))
        return super().form_valid(form)


class LogoutView(auth_views.LogoutView):
    next_page = "login"
