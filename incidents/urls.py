from django.urls import path

from incidents import views

app_name = "incidents"

urlpatterns = [
    path("", views.IncidentListView.as_view(), name="list"),
    path("new/", views.IncidentCreateView.as_view(), name="add"),
    path("<int:pk>/", views.IncidentDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.IncidentUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.IncidentDeleteView.as_view(), name="delete"),
]
