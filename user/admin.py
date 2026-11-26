from django.contrib import admin
from user_service.admin_filters import OntologyIdListFilter

from .models import (
    EmailLog,
    OAuthLoginTransaction,
    RoleModel,
    SearchSettingModel,
    UserModel,
    UserTokenModel,
)


@admin.register(UserModel)
class UserAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "client_ts")
    list_filter = ("client_ts",)
    show_facets = admin.ShowFacets.ALWAYS
    ordering = ("client_ts", "username")
    search_fields = ("username", "email")


@admin.register(UserTokenModel)
class UserTokenAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "user__client_ts", "created_at", "expires_at")
    list_filter = ("user__client_ts",)
    show_facets = admin.ShowFacets.ALWAYS
    ordering = ("user__client_ts", "name")


@admin.register(RoleModel)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "client_ts", "target_object_type", "target_object_id", "created_at")
    list_filter = ("client_ts",)
    show_facets = admin.ShowFacets.ALWAYS
    ordering = ("client_ts", "-created_at")


@admin.register(SearchSettingModel)
class SearchSettingAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "user__client_ts", "created_at")
    list_filter = ("user__client_ts",)
    show_facets = admin.ShowFacets.ALWAYS
    ordering = ("user__client_ts", "title")


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ("subject", "recipient", "client_ts", "notification_type", "status", "created_at")
    list_filter = ("client_ts", OntologyIdListFilter)
    show_facets = admin.ShowFacets.ALWAYS
    ordering = ("client_ts", "-created_at")


@admin.register(OAuthLoginTransaction)
class OAuthLoginTransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "auth_provider", "client_ts_id", "created_at", "expires_at")
    list_filter = ("client_ts_id",)
    show_facets = admin.ShowFacets.ALWAYS
    ordering = ("client_ts_id", "-created_at")
