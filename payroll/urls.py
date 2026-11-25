from django.urls import path

from payroll import views

app_name = "payroll"

urlpatterns = [
    path("", views.RunListView.as_view(), name="run_list"),
    path("new/", views.RunCreateView.as_view(), name="run_add"),
    path("<int:pk>/", views.RunDetailView.as_view(), name="run_detail"),
    path("<int:pk>/edit/", views.RunUpdateView.as_view(), name="run_edit"),

    path("<int:run_pk>/line/add/", views.LineCreateView.as_view(), name="line_add"),
    path("line/<int:pk>/edit/", views.LineUpdateView.as_view(), name="line_edit"),
    path("line/<int:pk>/delete/", views.LineDeleteView.as_view(), name="line_delete"),

    path("<int:run_pk>/populate/", views.PopulateFromEmployeesView.as_view(), name="populate"),
    path("<int:run_pk>/copy-previous/", views.CopyFromPreviousView.as_view(), name="copy_previous"),
    path("<int:run_pk>/finalise/", views.FinaliseView.as_view(), name="finalise"),
    path("<int:run_pk>/reopen/", views.ReopenView.as_view(), name="reopen"),

    path("<int:run_pk>/export.csv", views.ExportCsvView.as_view(), name="export_csv"),
    path("<int:run_pk>/export.xlsx", views.ExportXlsxView.as_view(), name="export_xlsx"),

    # Retrenchment (severance) payouts
    path("retrenchment/", views.RetrListView.as_view(), name="retr_list"),
    path("retrenchment/new/", views.RetrCreateView.as_view(), name="retr_add"),
    path("retrenchment/<int:pk>/", views.RetrDetailView.as_view(), name="retr_detail"),
    path("retrenchment/<int:pk>/edit/", views.RetrUpdateView.as_view(), name="retr_edit"),
    path("retrenchment/<int:batch_pk>/payment/add/", views.RetrPaymentCreateView.as_view(), name="retr_payment_add"),
    path("retrenchment/payment/<int:pk>/edit/", views.RetrPaymentUpdateView.as_view(), name="retr_payment_edit"),
    path("retrenchment/payment/<int:pk>/delete/", views.RetrPaymentDeleteView.as_view(), name="retr_payment_delete"),
    path("retrenchment/<int:batch_pk>/finalise/", views.RetrFinaliseView.as_view(), name="retr_finalise"),
    path("retrenchment/<int:batch_pk>/reopen/", views.RetrReopenView.as_view(), name="retr_reopen"),
    path("retrenchment/<int:batch_pk>/export.csv", views.RetrExportCsvView.as_view(), name="retr_export_csv"),
    path("retrenchment/<int:batch_pk>/export.xlsx", views.RetrExportXlsxView.as_view(), name="retr_export_xlsx"),
]
