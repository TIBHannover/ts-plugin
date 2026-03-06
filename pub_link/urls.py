from django.urls import path
from . import views
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    path("ping/", csrf_exempt(views.ping), name="ping"),
    path("create/", csrf_exempt(views.create_pub_link), name="create"),
]
