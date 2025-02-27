from django.urls import path
from . import views
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    path("ping/", views.ping, name="ping"),
    path("create/", csrf_exempt(views.create), name="create"),
    path("testshape/", views.testshape, name="testShape"),
    path("suggestion_exist/", views.suggestion_exist, name="suggestion_exist"),
]




