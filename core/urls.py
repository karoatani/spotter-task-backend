# urls.py
from django.urls import path
from .views import PlanTripView, TripRouteLogsView

urlpatterns = [
    path("api/plan-trip/", PlanTripView.as_view(), name="plan-trip"),
    path("trips/<int:trip_id>/daily-logs/", TripRouteLogsView.as_view(), name="trip-daily-logs"),
]
