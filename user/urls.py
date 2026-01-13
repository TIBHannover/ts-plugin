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
    path("apikey/create/", views.create_api_key, name="create_api_key"),
    path("apikey/update/", views.update_api_key, name="update_api_key"),
    path("apikey/delete/", views.delete_api_key, name="delete_api_key"),
    path("apikey/get/", views.get_api_keys, name="get_api_keys"),
]
