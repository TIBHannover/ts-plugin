from django.urls import path
from . import views
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    path(
        "is_entity_admin/", csrf_exempt(views.is_entity_admin), name="is_entity_admin"
    ),
    path(
        "is_system_admin/", csrf_exempt(views.is_system_admin), name="is_system_admin"
    ),
    path("send_test_email/", csrf_exempt(views.send_test_email), name="send_test_email"),
    path("metrics/", csrf_exempt(views.metrics), name="metrics"),
    path("stats/", csrf_exempt(views.get_stats), name="stats"),
]
