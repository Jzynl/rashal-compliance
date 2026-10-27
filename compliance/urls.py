from django.urls import path

from compliance import views

app_name = "compliance"

urlpatterns = [
    path("", views.TypeListView.as_view(), name="type_list"),
    path("matrix/", views.MatrixView.as_view(), name="matrix"),
    path("type/<int:pk>/", views.TypeDetailView.as_view(), name="type_detail"),
    path("obligation/<int:pk>/", views.ObligationDetailView.as_view(),
         name="obligation_detail"),
    path("period/<int:period_pk>/upload/", views.UploadDocumentView.as_view(),
         name="upload_document"),
    path("document/<int:pk>/", views.serve_document, name="document_serve"),
       path("add/", views.AddComplianceView.as_view(), name="add_compliance"),
]