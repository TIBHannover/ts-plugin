from user_service.libs.utils import create_json_response, is_valid_uuid
from django.views.decorators.http import require_http_methods
from user_service.libs.decorators import (
    authentication_required,
    error_handler_decorator,
)
from .models import TermSetModel, TermsModel
from user.models import UserModel
import json
from user_service.middlewares.request import get_username_from_request, get_headers_dict
from datetime import datetime as _time
from django.core.exceptions import BadRequest
from django.http import Http404, HttpResponseServerError
from django.db import transaction, IntegrityError
import uuid
from django.db.models import Q
from user.libs.auth import Auth
from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import api_view
from term_set.docs import (
    TermSetCreateRequestSerializer,
    TermSetUpdateRequestSerializer,
    TermSetGetRequestSerializer,
    TermSetCreateResponseSerializer,
    TermSetUpdateResponseSerializer,
    TermSetGetResponseSerializer,
    TermSetDeleteResponseSerializer,
    TermSetAddTermResponseSerializer,
    AddTermRequestSerializer,
    RemoveTermRequestSerializer,
    TermSetRemoveTermResponseSerializer,
)


@require_http_methods(["GET"])
def ping(request):
    return create_json_response({"response": "Pong"})


@swagger_auto_schema(
    tags=["TermSet"],
    method="post",
    request_body=TermSetCreateRequestSerializer,
    responses={
        200: TermSetCreateResponseSerializer,
        500: "Server Error",
    },
    operation_summary="Create a term set",
    operation_description="Creates a term set for a given ontology. Visibility can be 'me', 'internal', or 'public'.",
)
@api_view(["POST"])
@error_handler_decorator
@authentication_required
@require_http_methods(["POST"])
def create(request):
    payload = json.loads(request.body)
    username = get_username_from_request()
    name = payload["name"]
    description = payload.get("description", "")
    visibility = payload.get("visibility", "me")
    terms_json_list = payload.get("terms", [])
    user = UserModel.get_by_username(username=username)

    if name == "":
        raise BadRequest("termset name cannot be empty")

    try:
        with transaction.atomic():
            term_set = TermSetModel()
            term_set.id = str(uuid.uuid4())
            term_set.creator = user
            term_set.name = name
            term_set.created_at = _time.now()
            term_set.description = description
            term_set.visibility = visibility
            term_set.save()
            if not term_set.id:
                raise ValueError("data could not be saved.")
            terms_to_save = []
            for term in terms_json_list:
                term_model = TermsModel()
                term_model.iri = term["iri"]
                term_model.term_type = (
                    term["type"][0] if isinstance(term["type"], list) else term["type"]
                )
                term_model.metadata = term
                term_model.term_set = term_set
                terms_to_save.append(term_model)

            TermsModel.objects.bulk_create(terms_to_save)

    except IntegrityError:
        return HttpResponseServerError("data could not be saved.")

    return create_json_response({"term_set": term_set.to_dict()})


@swagger_auto_schema(
    tags=["TermSet"],
    method="get",
    query_serializer=TermSetGetRequestSerializer,
    responses={
        200: TermSetGetResponseSerializer,
        404: "Term set does not exist",
        500: "Server Error",
    },
    operation_summary="Get one or a list of term sets",
    operation_description="Get one or a list of term sets",
)
@api_view(["GET"])
@error_handler_decorator
@require_http_methods(["GET"])
def get(request, id=None):
    username = get_username_from_request()
    auth_object_dict = get_headers_dict()
    user = UserModel.get_by_username(username=username)
    user_id = user.id if user else None
    auth_object_dict["user_id"] = user_id
    auth = Auth(**auth_object_dict)
    if auth.user_is_guest():
        user_id = None

    if not id:
        # list of term sets
        term_sets = []
        if not user_id:
            # guest user. show only public term sets
            term_sets = TermSetModel.objects.filter(visibility="public").all()
        else:
            term_sets = TermSetModel.objects.filter(
                Q(visibility="internal")
                | Q(visibility="public")
                | (Q(visibility="me") & Q(creator=user))
            )

        return create_json_response(
            {"term_sets": [term_set.to_dict() for term_set in term_sets]}
        )

    if not is_valid_uuid(id):
        raise Http404("Term set does not exist")
    term_set = TermSetModel.objects.filter(id=id).first()
    if not term_set or not term_set.can_visit(user_id=user_id):
        raise Http404("Term set does not exist")

    return create_json_response({"term_set": term_set.to_dict()})


@swagger_auto_schema(
    tags=["TermSet"],
    method="put",
    request_body=TermSetUpdateRequestSerializer,
    responses={
        200: TermSetUpdateResponseSerializer,
        404: "Term set does not exist",
        500: "Server Error",
    },
    operation_summary="Update a term set",
    operation_description="Update a term set for a given term set id",
)
@api_view(["PUT"])
@error_handler_decorator
@authentication_required
@require_http_methods(["PUT"])
def update(request, id):
    if not is_valid_uuid(id):
        raise Http404("Terms set does not exist")
    payload = json.loads(request.body)
    username = get_username_from_request()
    name = payload["name"]
    description = payload.get("description", "")
    visibility = payload.get("visibility", "me")
    terms_json_list = payload.get("terms", [])
    user = UserModel.get_by_username(username=username)
    term_set = TermSetModel.objects.filter(id=id).first()
    if not term_set or not term_set.can_edit(user_id=user.id):
        raise Http404("Term set does not exist")

    if name == "":
        raise BadRequest("Term set name cannot be empty")

    try:
        with transaction.atomic():
            term_set.name = name
            term_set.updated_at = _time.now()
            term_set.description = description
            term_set.visibility = visibility
            term_set.save()
            terms_to_save = []
            term_set.terms.all().delete()
            for term in terms_json_list:
                term_model = TermsModel()
                term_model.iri = term["iri"]
                term_model.term_type = (
                    term["type"][0] if isinstance(term["type"], list) else term["type"]
                )
                term_model.metadata = term
                term_model.term_set = term_set
                terms_to_save.append(term_model)

            TermsModel.objects.bulk_create(terms_to_save)

    except IntegrityError:
        return HttpResponseServerError("data could not be updated.")

    return create_json_response({"term_set": term_set.to_dict()})


@swagger_auto_schema(
    tags=["TermSet"],
    method="delete",
    responses={
        200: TermSetDeleteResponseSerializer,
        404: "Term set does not exist",
        500: "Server Error",
    },
    operation_summary="Delete a term set",
    operation_description="Delete a term set for a given term set id",
)
@api_view(["DELETE"])
@error_handler_decorator
@authentication_required
@require_http_methods(["DELETE"])
def delete(request, id):
    if not is_valid_uuid(id):
        raise Http404("Term set does not exist")
    username = get_username_from_request()
    user = UserModel.get_by_username(username=username)
    term_set = TermSetModel.objects.filter(id=id).first()
    if not term_set or not term_set.can_edit(user_id=user.id):
        raise Http404("Term set does not exist")

    term_set.delete()
    return create_json_response({"deleted": True})


@swagger_auto_schema(
    tags=["TermSet"],
    method="put",
    request_body=AddTermRequestSerializer,
    responses={
        200: TermSetAddTermResponseSerializer,
        404: "Term set does not exist",
        500: "Server Error",
    },
    operation_summary="Add a term to a term set",
    operation_description="Add a term to a term set for a given term set id",
)
@api_view(["PUT"])
@error_handler_decorator
@authentication_required
@require_http_methods(["PUT"])
def add_term(request, setId):
    if not is_valid_uuid(setId):
        raise Http404("Terms set does not exist")
    username = get_username_from_request()
    payload = json.loads(request.body)
    term = payload.get("term", None)
    if not term:
        raise BadRequest("term is missing")

    term_set = TermSetModel.objects.filter(id=setId).first()
    user = UserModel.get_by_username(username=username)
    if not term_set or not term_set.can_edit(user_id=user.id):
        raise Http404("Term set does not exist")

    term_model = TermsModel()
    term_model.iri = term["iri"]
    term_model.term_type = (
        term["type"][0] if isinstance(term["type"], list) else term["type"]
    )
    term_model.metadata = term
    term_model.term_set = term_set
    term_model.save()
    return create_json_response({"added": True})


@swagger_auto_schema(
    tags=["TermSet"],
    method="delete",
    query_serializer=RemoveTermRequestSerializer,
    responses={
        200: TermSetRemoveTermResponseSerializer,
        404: "Term set does not exist",
        500: "Server Error",
    },
    operation_summary="Remove a term from a term set",
    operation_description="Remove a term from a term set for a given term set id",
)
@api_view(["DELETE"])
@error_handler_decorator
@authentication_required
@require_http_methods(["DELETE"])
def remove_term(request, setId):
    if not is_valid_uuid(setId):
        raise Http404("Terms set does not exist")
    username = get_username_from_request()
    termId = request.GET.get("termId", None)
    if not termId:
        raise BadRequest("term id is missing")

    term_set = TermSetModel.objects.filter(id=setId).first()
    user = UserModel.get_by_username(username=username)
    if not term_set or not term_set.can_edit(user_id=user.id):
        raise Http404("Term set does not exist")

    term_model = TermsModel.objects.filter(iri=termId, term_set=term_set).first()
    if not term_model:
        raise Http404("Term does not exist")
    term_model.delete()
    return create_json_response({"removed": True})
