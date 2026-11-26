from django.contrib import admin
from .models import NoteModel, NoteCommentModel


@admin.register(NoteModel)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("title", "creator", "creator__client_ts", "ontology_id", "visibility", "created_at")
    list_filter = ("creator__client_ts", "ontology_id")
    show_facets = admin.ShowFacets.ALWAYS
    ordering = ("creator__client_ts", "-created_at")


@admin.register(NoteCommentModel)
class NoteCommentAdmin(admin.ModelAdmin):
    list_display = ("id", "note", "creator", "creator__client_ts", "active", "created_at")
    list_filter = ("creator__client_ts", "note__ontology_id")
    show_facets = admin.ShowFacets.ALWAYS
    ordering = ("creator__client_ts", "-created_at")
