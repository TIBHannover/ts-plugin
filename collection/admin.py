from django.contrib import admin
from user_service.admin_filters import OntologyIdListFilter
from .models import CollectionModel


@admin.register(CollectionModel)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "owner__client_ts", "public", "created_at")
    list_filter = ("owner__client_ts", OntologyIdListFilter)
    show_facets = admin.ShowFacets.ALWAYS
    ordering = ("owner__client_ts", "title")
