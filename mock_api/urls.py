from django.urls import path
from . import views

urlpatterns = [
    path('api/report', views.mock_report, name='mock-report'),
    path('api/upload', views.mock_upload, name='mock-upload'),
]
