from django.urls import path
from . import views
from django.views.decorators.csrf import csrf_exempt as crsf_exempt

urlpatterns = [
    path(
        "get_parent_term/", crsf_exempt(views.get_parent_term), name="get_parent_term"
    ),
]
