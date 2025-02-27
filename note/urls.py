from django.urls import path
from . import views
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    path("ping/", views.ping, name="ping"),
    path("create/", csrf_exempt(views.create), name="create"),
    path("update/", csrf_exempt(views.update), name="update"),
    path("list/", views.list, name="list"),
    path("get/<int:note_id>/", views.get, name="get_note"),
    path("create_comment/", csrf_exempt(views.create_comment), name="create_comment"),
    path("update_comment/", csrf_exempt(views.update_comment), name="update_comment"),
    path("delete/", csrf_exempt(views.delete), name="delete"),
    path("update_pin/", csrf_exempt(views.update_pin), name="update"),
]
