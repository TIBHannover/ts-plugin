from django.urls import path
from . import views

urlpatterns = [
    path("agent/start/", views.start_agent, name="start_agent"),
]
