"""Swagger adapters for Django views; these patterns are never served as API routes."""

from importlib import import_module
import re

from django.urls import path
from drf_yasg import openapi
from drf_yasg.generators import OpenAPISchemaGenerator
from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import api_view


STRING = openapi.Schema(type=openapi.TYPE_STRING)
BOOLEAN = openapi.Schema(type=openapi.TYPE_BOOLEAN)
OBJECT = openapi.Schema(type=openapi.TYPE_OBJECT)
STRINGS = openapi.Schema(type=openapi.TYPE_ARRAY, items=STRING)


def body(required=(), **properties):
    return openapi.Schema(
        type=openapi.TYPE_OBJECT, properties=properties, required=list(required) or None
    )


def query(name, required=False, type=openapi.TYPE_STRING, **kwargs):
    return openapi.Parameter(name, openapi.IN_QUERY, type=type, required=required, **kwargs)


def operation(summary, request=None, parameters=(), result=None, public=False,
              description=""):
    responses = {
        200: openapi.Response("Success", body(_result=result or OBJECT)),
        400: "Invalid request",
        401: "Not Authorized",
        404: "Not found",
        500: "Server Error",
    }
    return {
        "operation_summary": summary,
        "operation_description": description,
        "request_body": request,
        "manual_parameters": list(parameters),
        "responses": responses,
        "security": [] if public else [{"ApiKey": []}],
    }


COLLECTION = body(
    ("title", "ontology_ids"),
    title=openapi.Schema(type="string", max_length=20),
    description=STRING, ontology_ids=STRINGS,
)
PURL = [query("purl", required=True)]


# Keys mirror the real URL patterns. Only API-key-compatible and public routes belong here.
OPERATIONS = {
    "collection": {
        "create/": {"post": operation("Create a collection", COLLECTION, result=body(collection=OBJECT))},
        "get/<int:collection_id>/": {"get": operation("Get a collection", result=body(collection=OBJECT))},
        "get_list/": {"get": operation("List owned collections", result=body(collections=openapi.Schema(type="array", items=OBJECT)))},
        "update/<int:collection_id>/": {"put": operation("Update a collection", COLLECTION, result=body(collection=OBJECT))},
        "delete/<int:collection_id>/": {"delete": operation("Delete a collection", result=body(deleted=BOOLEAN))},
    },
    "pub_link": {
        "create/": {"post": operation("Create a publication link", body(("doi", "ontology_id"), doi=STRING, ontology_id=STRING), result=body(created=OBJECT))},
        "get/<str:ontology_id>/": {"get": operation("List ontology publications", public=True, result=body(publications=openapi.Schema(type="array", items=OBJECT)))},
        "delete/<int:id>/": {"delete": operation("Delete an owned publication link", result=body(deleted=BOOLEAN))},
    },
    "ontologysuggestion": {
        "create/": {"post": operation("Suggest an ontology or collection addition", body(
            ("email", "username", "reason", "name", "purl"), email=STRING, username=STRING,
            reason=STRING, name=STRING, purl=STRING, collection_ids=STRING, collection_suggestion=BOOLEAN,
        ), result=body(response=STRING), description="Additional ontology metadata fields may be supplied when required by SHACL validation.")},
        "testshape/": {"get": operation("Validate ontology shape", parameters=PURL, result=body(response=OBJECT))},
        "suggestion_exist/": {"get": operation("Check for an existing ontology suggestion", parameters=PURL, result=body(exist=BOOLEAN))},
        "purl_is_valid/": {"get": operation("Validate an ontology PURL", parameters=PURL, public=True, result=body(valid=BOOLEAN, reason=STRING))},
        "adopter_create/": {"post": operation("Submit an ontology adopter request", body(
            ("email", "username", "name", "purl"), email=STRING, username=STRING, name=STRING,
            purl=STRING, adopter_type=STRING, adopter_name=STRING, usage_description=STRING, usage_channel=STRING,
        ), result=body(response=STRING))},
    },
    "contact": {
        "create/": {"post": operation("Submit a contact request", body(
            ("title", "description", "email", "name", "type", "safeQuestion", "safeAnswer", "appError"),
            title=STRING, description=STRING, email=STRING, name=STRING,
            type=openapi.Schema(type="string", enum=["1", "2"]),
            safeQuestion=STRING, safeAnswer=STRING, appError=BOOLEAN,
        ), result=body(response=STRING), description="The API key supplies the terminology-service context. safeQuestion must contain an addition such as '2+3'; safeAnswer must equal its sum.")},
    },
}


MODULES = {"ontologysuggestion": "ontology_suggestion"}
TAGS = {
    "term_set": "TermSet",
    "note": "Note",
    "ontologysuggestion": "OntologySuggestion",
    "collection": "Collection",
    "contact": "Contact",
    "pub_link": "Pub Link",
}


class SchemaGenerator(OpenAPISchemaGenerator):
    def get_schema(self, request=None, public=False):
        schema = super().get_schema(request=request, public=public)
        schema.tags = [{"name": tag} for tag in TAGS.values()]
        return schema


def get_schema_patterns():
    patterns = []
    for prefix in TAGS:
        for pattern in import_module(f"{MODULES.get(prefix, prefix)}.urls").urlpatterns:
            route = str(pattern.pattern)
            callback = pattern.callback
            if hasattr(callback, "cls"):
                patterns.append(path(f"{prefix}/{route}", callback, name=pattern.name))
                continue
            operations = OPERATIONS.get(prefix, {}).get(route)
            if not operations:
                continue
            # DRF is used only for schema inspection, leaving the live Django callback untouched.
            adapter = api_view([method.upper() for method in operations])(callback)
            adapter.cls.authentication_classes = []
            adapter.cls.permission_classes = []
            for method, metadata in operations.items():
                adapter = swagger_auto_schema(
                    method=method, tags=[TAGS[prefix]],
                    operation_id=re.sub(r"\W+", "_", f"{prefix}/{route}/{method}"),
                    **metadata,
                )(adapter)
            patterns.append(path(f"{prefix}/{route}", adapter, name=pattern.name))
    return patterns
