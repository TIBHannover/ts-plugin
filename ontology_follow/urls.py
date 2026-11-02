from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from ontology_follow import views


urlpatterns = [
    path("", csrf_exempt(views.follows), name="ontology_follows"),
]
