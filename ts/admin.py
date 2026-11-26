from django.contrib import admin

from .models import HarvestFailureModel, TermDatasetLinkModel


@admin.register(TermDatasetLinkModel)
class TermDatasetLinkAdmin(admin.ModelAdmin):
    list_display = ("curie", "term_label", "ontology_id", "dataset_title", "repo_name", "created_at")
    list_filter = ("ontology_id",)
    show_facets = admin.ShowFacets.ALWAYS


@admin.register(HarvestFailureModel)
class HarvestFailureAdmin(admin.ModelAdmin):
    list_display = ("dataset_title", "error_code", "created_at")
