from user.models import UserModel
from .models import CollectionModel
from datetime import datetime as _time
from user_service.libs.decorators import (
    error_handler_decorator,
    authentication_required,
)
from django.views.decorators.http import require_http_methods
from user_service.libs.utils import create_json_response
from user_service.middlewares.request import (
    get_username_from_request,
)
from user_service.middlewares.client_id import get_client_id_from_request
from django.http import HttpResponseBadRequest, Http404
import json


@require_http_methods(["GET"])
def ping(request):
    return create_json_response({"response": "Pong"})


@error_handler_decorator
@authentication_required
@require_http_methods(["POST"])
def create(request):
    username = get_username_from_request()
    frontend_id = get_client_id_from_request()
    user = UserModel.objects.filter(username=username, client_ts=frontend_id).first()
    payload = json.loads(request.body)
    title = payload["title"]
    title = title.strip()
    description = payload.get("description")
    ontology_ids = payload["ontology_ids"]
    if title == "" or len(ontology_ids) == 0:
        return HttpResponseBadRequest("title and ontology_ids are required")

    if len(title) > 20:
        return HttpResponseBadRequest("title must be less than 20 characters")

    collection_model = CollectionModel(
        title=title,
        owner=user,
        created_at=_time.now(),
        description=description,
        ontology_ids=ontology_ids,
    )

    collection_model.save()
    if collection_model.id:
        return create_json_response({"collection": collection_model.to_dict()})

    return HttpResponseBadRequest("collection already exists")


@error_handler_decorator
@authentication_required
@require_http_methods(["GET"])
def get(request, collection_id):
    username = get_username_from_request()
    frontend_id = get_client_id_from_request()
    user = UserModel.objects.filter(username=username, client_ts=frontend_id).first()
    collection = CollectionModel.objects.filter(id=collection_id).first()
    if not collection or not collection.can_visit_edit(user.id):
        raise Http404("Collection not found")

    return create_json_response({"collection": collection.to_dict()})


@error_handler_decorator
@authentication_required
@require_http_methods(["GET"])
def get_list(request):
    username = get_username_from_request()
    frontend_id = get_client_id_from_request()
    user = UserModel.objects.filter(username=username, client_ts=frontend_id).first()
    collections = user.user_collections.all()
    return create_json_response({"collections": [col.to_dict() for col in collections]})


@error_handler_decorator
@authentication_required
@require_http_methods(["PUT"])
def update(request, collection_id):
    username = get_username_from_request()
    frontend_id = get_client_id_from_request()
    user = UserModel.objects.filter(username=username, client_ts=frontend_id).first()

    payload = json.loads(request.body)
    ontology_ids = payload["ontology_ids"]
    description = payload.get("description")
    title = payload.get("title")
    title = title.strip()
    if title == "" or len(ontology_ids) == 0:
        return HttpResponseBadRequest("title and ontology_ids are required")

    if len(title) > 20:
        return HttpResponseBadRequest("title must be less than 20 characters")

    collection_model = CollectionModel(
        title=title,
        description=description,
        updated_at=_time.now(),
        owner=user,
        ontology_ids=ontology_ids,
    )

    collection = collection_model.update(collection_id=collection_id)
    if not collection:
        raise Http404("collection not found")

    return create_json_response({"collection": collection})


@error_handler_decorator
@authentication_required
@require_http_methods(["DELETE"])
def delete(request, collection_id):
    username = get_username_from_request()
    frontend_id = get_client_id_from_request()
    user = UserModel.objects.filter(username=username, client_ts=frontend_id).first()
    collection = CollectionModel.objects.filter(id=collection_id).first()
    if not collection or not collection.can_visit_edit(user.id):
        raise Http404("collection not found")

    collection.delete()
    return create_json_response({"deleted": True})
