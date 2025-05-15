from django.urls import path
from . import views
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    path("ping/", views.ping, name="ping"),
    path("create/", csrf_exempt(views.create), name="create"),
    path("update/<int:id>/", csrf_exempt(views.update), name="update"),
    path("delete/<int:id>/", csrf_exempt(views.delete), name="delete"),
    path("get/<int:id>/", csrf_exempt(views.get), name="get"),
    path("get/", csrf_exempt(views.get), name="get"),
]
