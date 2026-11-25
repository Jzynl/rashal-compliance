from django.urls import path

from foundation import views

app_name = "foundation"

urlpatterns = [
    path("", views.EmployeeListView.as_view(), name="employee_list"),
    path("add/", views.EmployeeCreateView.as_view(), name="employee_add"),
    path("statutory/", views.StatutoryListView.as_view(), name="statutory_list"),
    path("credentials/", views.CredentialListView.as_view(), name="credential_list"),
    path("credentials/add/", views.CredentialCreateView.as_view(), name="credential_add"),
    path("credentials/<int:pk>/edit/", views.CredentialUpdateView.as_view(), name="credential_edit"),
    path("credentials/<int:pk>/delete/", views.CredentialDeleteView.as_view(), name="credential_delete"),
    path("<int:pk>/", views.EmployeeDetailView.as_view(), name="employee_detail"),
    path("<int:pk>/edit/", views.EmployeeUpdateView.as_view(), name="employee_edit"),
]
