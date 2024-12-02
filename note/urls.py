from django.urls import path
from . import views

urlpatterns = [
    path("ping/", views.ping, name="ping"),
    path("create/", views.create, name="create"),
    path("update/", views.update, name="update"),
    path("list/", views.list, name="list"),
    path("get/<int:note_id>/", views.get, name="get_note"),
    path("create_comment/", views.create_comment, name="create_comment"),
    path("update_comment/", views.update_comment, name="update_comment"),
    path("delete/", views.delete, name="delete"),
    path("update_pin/", views.update_pin, name="update_pin"),
]
