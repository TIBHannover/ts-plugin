from django.contrib import admin
from .models import TermSetModel, TermsModel


@admin.register(TermSetModel)
class TermSetAdmin(admin.ModelAdmin):
    list_display = ("name", "creator", "creator__client_ts", "visibility", "created_at")
    list_filter = ("creator__client_ts",)
    show_facets = admin.ShowFacets.ALWAYS
    ordering = ("creator__client_ts", "name")


@admin.register(TermsModel)
class TermsAdmin(admin.ModelAdmin):
    list_display = ("iri", "term_type", "term_set", "term_set__creator__client_ts")
    list_filter = ("term_set__creator__client_ts",)
    list_select_related = ("term_set__creator",)
    show_facets = admin.ShowFacets.ALWAYS
    ordering = ("term_set__creator__client_ts", "iri")
