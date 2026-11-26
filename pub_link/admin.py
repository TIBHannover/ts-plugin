from django.contrib import admin

from .models import PubLinkModel


@admin.register(PubLinkModel)
class PubLinkAdmin(admin.ModelAdmin):
    list_display = ("doi", "ontology_id", "creator", "creator__client_ts", "created_at")
    list_filter = ("creator__client_ts", "ontology_id")
    show_facets = admin.ShowFacets.ALWAYS
    ordering = ("creator__client_ts", "-created_at")
