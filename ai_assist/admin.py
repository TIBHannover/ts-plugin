from django.contrib import admin

from .models import AiAssistModelOutput, AiAssistSession, AiAssistUserInput, Ontology


class ReadOnlyLogInline(admin.TabularInline):
    extra = 0
    can_delete = False
    readonly_fields = ("sequence", "content", "created_at")

    def has_add_permission(self, request, obj=None):
        return False


class AiAssistUserInputInline(ReadOnlyLogInline):
    model = AiAssistUserInput


class AiAssistModelOutputInline(ReadOnlyLogInline):
    model = AiAssistModelOutput


@admin.register(AiAssistSession)
class AiAssistSessionAdmin(admin.ModelAdmin):
    list_display = (
        "run_id",
        "user",
        "user__client_ts",
        "workflow",
        "context_size",
        "total_tokens",
        "cost_usd",
        "created_at",
    )
    list_filter = ("user__client_ts", "workflow", "created_at")
    list_select_related = ("user",)
    show_facets = admin.ShowFacets.ALWAYS
    ordering = ("user__client_ts", "-created_at")
    search_fields = ("run_id", "user__username")
    readonly_fields = (
        "run_id",
        "user",
        "workflow",
        "context_size",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "cost_usd",
        "created_at",
    )
    inlines = (AiAssistUserInputInline, AiAssistModelOutputInline)

    def has_add_permission(self, request):
        return False


@admin.register(AiAssistUserInput, AiAssistModelOutput)
class AiAssistLogAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "session__user__client_ts", "sequence", "created_at")
    list_filter = ("session__user__client_ts",)
    list_select_related = ("session__user",)
    show_facets = admin.ShowFacets.ALWAYS
    ordering = ("session__user__client_ts", "-created_at", "sequence")
    readonly_fields = ("session", "sequence", "content", "created_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Ontology)
class OntologyAdmin(admin.ModelAdmin):
    list_display = ("ontologyId", "label", "repo_url", "loaded")
    list_filter = ("ontologyId",)
    show_facets = admin.ShowFacets.ALWAYS
