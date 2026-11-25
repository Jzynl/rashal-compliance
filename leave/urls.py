from django.urls import path

from leave import views

app_name = "leave"

urlpatterns = [
    path("", views.BalanceListView.as_view(), name="balance_list"),
    path("add/", views.BalanceCreateView.as_view(), name="balance_add"),
    path("<int:pk>/edit/", views.BalanceUpdateView.as_view(), name="balance_edit"),
    path("<int:pk>/delete/", views.BalanceDeleteView.as_view(), name="balance_delete"),

    path("types/", views.LeaveTypeListView.as_view(), name="type_list"),
    path("types/add/", views.LeaveTypeCreateView.as_view(), name="type_add"),
    path("types/<int:pk>/edit/", views.LeaveTypeUpdateView.as_view(), name="type_edit"),
]
