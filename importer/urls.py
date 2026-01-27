# importer/urls.py
from django.urls import path
from .views import UploadCSVView, DashboardView, ErrorLogView, ProgressView, ExportDataView

app_name = 'importer'

urlpatterns = [
    path('', UploadCSVView.as_view(), name='upload_csv'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('errors/<int:task_id>/', ErrorLogView.as_view(), name='error_log'),
    path('progress/<int:task_id>/', ProgressView.as_view(), name='progress'),
    path('export/', ExportDataView.as_view(), name='export_data'),
]
