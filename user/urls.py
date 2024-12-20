from django.urls import path
from . import views

urlpatterns = [
    path("ping/", views.ping, name="ping"),
    path("login/", views.login, name="login"),
    path("validate_login/", views.validate_login, name="validate_login"),
    path("settings/", views.save_settings, name="settings"),
    path("search_setting/", views.SearchSettings.as_view(), name="search_setting"),
    path("search_setting/<int:id>/", views.SearchSettings.as_view(), name="search_setting"),
]
