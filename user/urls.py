from django.urls import path
from . import views
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    path("ping/", views.ping, name="ping"),
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),
    path("validate_login/", views.validate_login, name="validate_login"),
    path("settings/", csrf_exempt(views.save_settings), name="settings"),
    path(
        "search_setting/",
        csrf_exempt(views.SearchSettings.as_view()),
        name="search_setting",
    ),
    path(
        "search_setting/<int:id>/",
        csrf_exempt(views.SearchSettings.as_view()),
        name="search_setting",
    ),
]
