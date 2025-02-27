from django.urls import path
from . import views
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    path("create/", csrf_exempt(views.create_report), name="create"),
    path("resolve/", csrf_exempt(views.resolve_report), name="resolve"),
    path("list/", views.report_list, name="list"),
]
