from django.shortcuts import render


def today(request):
    return render(request, "core/today.html", {"nav": "today"})


def settings_home(request):
    return render(request, "core/settings.html", {"nav": "settings"})
