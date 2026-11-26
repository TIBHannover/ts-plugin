from django.contrib import admin

from .models import OntologyFollowModel


@admin.register(OntologyFollowModel)
class OntologyFollowAdmin(admin.ModelAdmin):
    list_display = ("ontology_id", "user", "user__client_ts", "created_at")
    list_filter = ("user__client_ts", "ontology_id")
    show_facets = admin.ShowFacets.ALWAYS
    ordering = ("user__client_ts", "ontology_id")
