from django.urls import path
from . import views
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    path("agent/start/", csrf_exempt(views.start_agent), name="start_agent"),
]
