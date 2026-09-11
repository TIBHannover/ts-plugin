from django.contrib import admin

from .models import AiAssistModelOutput, AiAssistSession, AiAssistUserInput


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
        "workflow",
        "context_size",
        "total_tokens",
        "created_at",
    )
    list_filter = ("workflow", "created_at")
    search_fields = ("run_id", "user__username")
    readonly_fields = (
        "run_id",
        "user",
        "workflow",
        "context_size",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "created_at",
    )
    inlines = (AiAssistUserInputInline, AiAssistModelOutputInline)

    def has_add_permission(self, request):
        return False
