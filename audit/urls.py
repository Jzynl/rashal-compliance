from django.urls import path

from audit import views

app_name = "audit"

urlpatterns = [
    path("", views.AuditListView.as_view(), name="audit_list"),
    path("new/", views.AuditCreateView.as_view(), name="audit_add"),
    path("<int:pk>/", views.AuditDetailView.as_view(), name="audit_detail"),
    path("<int:pk>/edit/", views.AuditUpdateView.as_view(), name="audit_edit"),
    path("<int:pk>/checklist/save/", views.ChecklistSaveView.as_view(), name="checklist_save"),
    path("<int:pk>/delete/", views.AuditDeleteView.as_view(), name="audit_delete"),

    path("<int:audit_pk>/finding/add/", views.FindingCreateView.as_view(), name="finding_add"),
    path("finding/<int:pk>/edit/", views.FindingUpdateView.as_view(), name="finding_edit"),
    path("finding/<int:pk>/delete/", views.FindingDeleteView.as_view(), name="finding_delete"),
]
