"""Parking lot administration routes."""

from django.urls import path

from vps.lots import views

app_name = "lots"

urlpatterns = [
    path("", views.lot_list, name="list"),
    path("map/", views.lot_map, name="map"),
    path("map/parked.json", views.parked_vehicles_json, name="map_parked"),
    path("<int:lot_id>/map/state.json", views.lot_map_state_json, name="map_state"),
    path("occupancy/", views.occupancy, name="occupancy"),
    path("new/", views.lot_create, name="create"),
    path("<int:pk>/edit/", views.lot_edit, name="edit"),
    path("<int:pk>/archive/", views.lot_archive, name="archive"),
    path("<int:pk>/restore/", views.lot_restore, name="restore"),
    path("<int:pk>/block/", views.block_slot, name="block"),
    path("tariffs/", views.tariff_list, name="tariffs"),
    path("tariffs/save/", views.tariff_create, name="tariff_create"),
]
