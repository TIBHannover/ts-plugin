from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls), 
    path("user/", include("user.urls")),
    path("report/", include("report.urls")),
    path("ontologysuggestion/", include("ontology_suggestion.urls")),
    path("note/", include("note.urls")),
]

