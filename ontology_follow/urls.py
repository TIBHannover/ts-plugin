from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from ontology_follow import views


urlpatterns = [
    path("unfollow/", csrf_exempt(views.unfollow_email), name="ontology_unfollow_email"),
    path("", csrf_exempt(views.follows), name="ontology_follows"),
]
