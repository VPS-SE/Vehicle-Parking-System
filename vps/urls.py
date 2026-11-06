"""URL routes for the VPS project."""

from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path

from vps.accounts.views import home
from vps.views import healthz

urlpatterns = [
    path("", home, name="home"),
    path("accounts/", include("vps.accounts.urls")),
    path("vehicles/", include("vps.vehicles.urls")),
    path("lots/", include("vps.lots.urls")),
    path("reservations/", include("vps.reservations.urls")),
    path("gate/", include("vps.gate.urls")),
    path("reports/", include("vps.reports.urls")),
    path("billing/", include("vps.billing.urls")),
    path("admin/", admin.site.urls),
    path("healthz", healthz, name="healthz"),
]

# Gunicorn does not serve static files itself; keep the admin styled in development.
if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
