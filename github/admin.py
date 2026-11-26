from django.contrib import admin
from .models import GithubIssueRequestModel


@admin.register(GithubIssueRequestModel)
class GithubIssueRequestAdmin(admin.ModelAdmin):
    list_display = ("issue_title", "user", "client_ts", "ontology_id", "issue_type", "created_at")
    list_filter = ("client_ts", "ontology_id")
    show_facets = admin.ShowFacets.ALWAYS
    ordering = ("client_ts", "-created_at")
