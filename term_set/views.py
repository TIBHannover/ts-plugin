from user_service.libs.utils import create_json_response
from django.views.decorators.http import require_http_methods
from user_service.libs.decorators import (
    authentication_required,
    error_handler_decorator,
)
from .models import TermSetModel, TermsModel
from user.models import UserModel
import json
from user_service.middlewares.request import (
    get_client_id_from_request,
    get_username_from_request,
)
from datetime import datetime as _time
from django.core.exceptions import BadRequest
from django.http import HttpResponseServerError
from django.db import transaction, IntegrityError
import uuid


@require_http_methods(["GET"])
def ping(request):
    return create_json_response({"response": "Pong"})


@error_handler_decorator
@authentication_required
@require_http_methods(["POST"])
def create(request):
    payload = json.loads(request.body)
    frontend_id = get_client_id_from_request()
    username = get_username_from_request()
    name = payload["name"]
    description = payload.get("description", "")
    visibility = payload.get("visibility", "me")
    terms_json_list = payload.get("terms", [])
    if len(terms_json_list) == 0:
        raise BadRequest("set cannot be empty.")

    try:
        with transaction.atomic():
            user = UserModel.objects.filter(
                username=username, client_ts=frontend_id
            ).first()
            term_set = TermSetModel()
            term_set.id = str(uuid.uuid4())
            term_set.creator = user
            term_set.name = name
            term_set.created_at = _time.now()
            term_set.description = description
            term_set.visibility = visibility
            term_set.save()
            if not term_set.id:
                raise ValueError("term set failed to save.")
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
        raise
        return HttpResponseServerError("data could not be saved.")

    return create_json_response({"term_set": term_set.to_dict()})
