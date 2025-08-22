from django.urls import path
from . import views
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    path("ping/", views.ping, name="ping"),
    path("create/", csrf_exempt(views.create), name="create"),
    path("update/<str:id>/", csrf_exempt(views.update), name="update"),
    path("delete/<str:id>/", csrf_exempt(views.delete), name="delete"),
    path("get/<str:id>/", csrf_exempt(views.get), name="get"),
    path("get/", csrf_exempt(views.get), name="get"),
    path("<str:setId>/add_term/", csrf_exempt(views.add_term), name="add_term"),
    path(
        "<str:setId>/remove_term",
        csrf_exempt(views.remove_term),
        name="remove_term",
    ),
]
