from django.urls import path
from . import views
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    path("ping/", views.ping, name="ping"),
    path("get", csrf_exempt(views.get), name="get"),
    path("repos_list/", csrf_exempt(views.get_repos_list), name="repos_list"),
    path(
        "failed_harvests/",
        csrf_exempt(views.get_failed_harvests),
        name="failed_harvests",
    ),
    # path(
    #     "links/",
    #     csrf_exempt(views.get_term_dataset_links),
    #     name="term_dataset_links",
    # ),
    # path(
    #     "delete/",
    #     csrf_exempt(views.delete_term_dataset_link),
    #     name="delete_term_dataset_link",
    # ),
]
