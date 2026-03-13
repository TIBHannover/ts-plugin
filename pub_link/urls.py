from django.urls import path
from . import views
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    path("ping/", csrf_exempt(views.ping), name="ping"),
    path("create/", csrf_exempt(views.create_pub_link), name="create"),
    path(
        "get/<str:ontology_id>/", csrf_exempt(views.get_pub_link), name="get_pub_links"
    ),
    path(
        "delete/<int:id>/", csrf_exempt(views.delete_pub_link), name="delete_pub_link"
    ),
]
