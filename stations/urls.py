from django.urls import path

from stations import views

app_name = "stations"

urlpatterns = [
    path("", views.StationListView.as_view(), name="list"),
    path("<int:pk>/", views.StationDetailView.as_view(), name="detail"),
]
