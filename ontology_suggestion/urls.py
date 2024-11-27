from django.urls import path
from . import views

urlpatterns = [
    path("ping/", views.ping, name="ping"),
    path("create/", views.create, name="create"),
    path("testshape/", views.testShape, name="testShape"),
    path("suggestion_exist/", views.suggestion_exist, name="suggestion_exist"),
]




