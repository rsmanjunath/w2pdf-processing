from django.urls import path
from .views import W2PDFUploadView

urlpatterns = [
    path('upload/', W2PDFUploadView.as_view(), name='w2pdf-upload'),]
