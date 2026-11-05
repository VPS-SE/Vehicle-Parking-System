"""Billing routes."""

from django.urls import path

from vps.billing import views

app_name = "billing"

urlpatterns = [
    path("waivers/", views.waivers, name="waivers"),
    path("waivers/<int:charge_id>/", views.waive, name="waive"),
]
