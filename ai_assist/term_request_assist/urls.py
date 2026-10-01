from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from . import views

urlpatterns = [
    path("agent/start/", csrf_exempt(views.start_agent), name="start_agent"),
    path(
        "term-request/start/",
        csrf_exempt(views.start_term_request),
        name="start_term_request",
    ),
]
