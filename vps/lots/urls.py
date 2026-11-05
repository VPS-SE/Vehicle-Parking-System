"""Parking lot administration routes."""

from django.urls import path

from vps.lots import views

app_name = "lots"

urlpatterns = [
    path("", views.lot_list, name="list"),
    path("occupancy/", views.occupancy, name="occupancy"),
    path("new/", views.lot_create, name="create"),
    path("<int:pk>/edit/", views.lot_edit, name="edit"),
    path("<int:pk>/archive/", views.lot_archive, name="archive"),
    path("<int:pk>/restore/", views.lot_restore, name="restore"),
    path("<int:pk>/block/", views.block_slot, name="block"),
    path("tariffs/", views.tariff_list, name="tariffs"),
    path("tariffs/save/", views.tariff_create, name="tariff_create"),
]
