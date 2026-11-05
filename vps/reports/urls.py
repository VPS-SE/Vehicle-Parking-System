"""Report routes."""

from django.urls import path

from vps.reports import views

app_name = "reports"

urlpatterns = [
    path("revenue/", views.revenue, name="revenue"),
    path("revenue.csv", views.revenue_csv, name="revenue_csv"),
    path("occupancy/", views.occupancy, name="occupancy"),
    path("occupancy.csv", views.occupancy_csv, name="occupancy_csv"),
]
