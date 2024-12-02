from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin_panel/", admin.site.urls), 
    path("user/", include("user.urls")),
    path("report/", include("report.urls")),
    path("ontologysuggestion/", include("ontology_suggestion.urls")),
    path("note/", include("note.urls")),
    path("github/", include("github.urls")),
    path("contact/", include("contact.urls")),
    path("collection/", include("collection.urls")),
    path("admin/", include("admin.urls")),
]

