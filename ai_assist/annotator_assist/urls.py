from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from .views import annotate, annotation_status

urlpatterns = [
    path("annotate/", csrf_exempt(annotate), name="annotate_dataset"),
    path("annotate/status/<uuid:run_id>/", annotation_status, name="annotation_status"),
]
