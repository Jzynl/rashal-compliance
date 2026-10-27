from django.contrib import admin
from django.urls import include, path

# Note: no static() call for MEDIA_ROOT. Compliance documents are private
# and are streamed only through compliance.views.serve_document, which
# checks station scope first. Do not add a media route here.

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("compliance/", include("compliance.urls")),
    path("stations/", include("stations.urls")),
    path("", include("dashboard.urls")),
]

admin.site.site_header = "Rashal Energies · Compliance"
admin.site.site_title = "Rashal Compliance"
admin.site.index_title = "Setup"
