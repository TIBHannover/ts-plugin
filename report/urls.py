from django.urls import path
from . import views

urlpatterns = [
    path("ping/", views.ping, name="ping"),
    path("create/", views.create_report, name="create"),
    path("resolve/", views.resolve_report, name="resolve"),
    path("list/", views.report_list, name="list"),
]
