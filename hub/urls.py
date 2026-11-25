from django.urls import path

from hub import views

app_name = "hub"

urlpatterns = [
    path("", views.HubView.as_view(), name="home"),
]
