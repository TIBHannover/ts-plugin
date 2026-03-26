from django.urls import path
from . import views
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    path("ping/", views.ping, name="ping"),
    path(
        "links/",
        csrf_exempt(views.get_term_dataset_links),
        name="term_dataset_links",
    ),
    path(
        "delete/",
        csrf_exempt(views.delete_term_dataset_link),
        name="delete_term_dataset_link",
    ),
]
