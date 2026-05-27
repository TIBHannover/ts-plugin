from django.urls import path
from . import views
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    path("ping/", views.ping, name="ping"),
    path("close_endpoint/", views.close_endpoint, name="close_endpoint"),
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
    path("apikey/create/", csrf_exempt(views.create_api_key), name="create_api_key"),
    path("apikey/update/", csrf_exempt(views.update_api_key), name="update_api_key"),
    path("apikey/delete/", csrf_exempt(views.delete_api_key), name="delete_api_key"),
    path("apikey/get/", csrf_exempt(views.get_api_keys), name="get_api_keys"),
    path("login/get_code/", views.login_with_device_flow, name="get_login_code"),
    path(
        "login/send_term_request/",
        csrf_exempt(views.send_term_request),
        name="send_term_request",
    ),
]
