from django.contrib import admin

from .models import OntologySuggestionModel

@admin.register(OntologySuggestionModel)
class OntologySuggestionAdmin(admin.ModelAdmin):
    list_display = ("ontology_purl", "user", "user__client_ts", "status", "created_at")
    list_filter = ("user__client_ts", "ontology_purl")
    show_facets = admin.ShowFacets.ALWAYS
    ordering = ("user__client_ts", "-created_at")
