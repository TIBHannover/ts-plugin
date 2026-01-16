from django.contrib import admin
from django.urls import path, include, re_path
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions
from user_service import settings
from django.conf.urls.static import static


schema_view = get_schema_view(
    openapi.Info(
        title="Snippets API",
        default_version="v1",
        description="Test description",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="contact@snippets.local"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
    authentication_classes=(),
)

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
    path("term_set/", include("term_set.urls")),
    path(
        "swagger.<format>/", schema_view.without_ui(cache_timeout=0), name="schema-json"
    ),
    path(
        "swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
