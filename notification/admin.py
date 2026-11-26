from django.contrib import admin

from .models import NotificationLog, OntologyGitHubCache


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ("trigger", "recipient", "success", "created_at")


@admin.register(OntologyGitHubCache)
class OntologyGitHubCacheAdmin(admin.ModelAdmin):
    list_display = ("ontology_id", "metadata_expires_at", "updates_expires_at", "window_end")
    list_filter = ("ontology_id",)
    show_facets = admin.ShowFacets.ALWAYS
