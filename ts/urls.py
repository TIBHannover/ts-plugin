from django.urls import path
from . import views
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    path("ping/", views.ping, name="ping"),
    path(
        "harvest_datasets_terms_links/",
        csrf_exempt(views.harvest_datasets_terms_links),
        name="harvest_datasets_terms_links",
    ),
]
