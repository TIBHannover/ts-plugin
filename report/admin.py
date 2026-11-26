from django.contrib import admin

from .models import ReportModel

@admin.register(ReportModel)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("id", "reported_object_type", "reported_object_id", "reporter", "client_ts", "status", "created_at")
    list_filter = ("client_ts",)
    show_facets = admin.ShowFacets.ALWAYS
    ordering = ("client_ts", "-created_at")
