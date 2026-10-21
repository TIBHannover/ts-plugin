from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from .views import start_search

urlpatterns = [
    path("search/start/", csrf_exempt(start_search), name="start_search"),
]
