import json

from django.core.exceptions import BadRequest, PermissionDenied
from django.views.decorators.http import require_http_methods

from ontology_follow.models import OntologyFollowModel
from user.models import UserModel
from user_service.libs.decorators import authentication_required, error_handler_decorator
from user_service.libs.utils import create_json_response
from user_service.middlewares.request import get_username_from_request


@error_handler_decorator
@authentication_required
@require_http_methods(["GET", "POST", "PATCH", "DELETE"])
def follows(request):
    user = UserModel.get_by_username(get_username_from_request())
    if not user:
        raise PermissionDenied("Not Authorized")
    if request.method == "GET":
        follows = list(user.ontology_follows.order_by("ontology_id").values(
            "ontology_id", "notify_note", "notify_issue", "notify_publication"
        ))
        return create_json_response({
            "ontology_ids": [follow["ontology_id"] for follow in follows],
            "follows": follows,
        })
    try:
        payload = json.loads(request.body)
    except ValueError:
        raise BadRequest("Invalid JSON body")
    ontology_id = payload.get("ontology_id") if isinstance(payload, dict) else None
    if not isinstance(ontology_id, str) or not ontology_id.strip():
        raise BadRequest("ontology_id must be a non-empty string")
    ontology_id = ontology_id.strip().lower()
    if request.method in ("POST", "PATCH"):
        preferences = {}
        for field in ("notify_note", "notify_issue", "notify_publication"):
            if field in payload:
                if not isinstance(payload[field], bool):
                    raise BadRequest(f"{field} must be a boolean")
                preferences[field] = payload[field]
        if request.method == "PATCH":
            if not user.ontology_follows.filter(ontology_id=ontology_id).update(**preferences):
                raise BadRequest("Ontology is not followed or no preferences were provided")
        else:
            OntologyFollowModel.objects.update_or_create(
                user=user, ontology_id=ontology_id, defaults=preferences
            )
    else:
        user.ontology_follows.filter(ontology_id=ontology_id).delete()
    return create_json_response({
        "ontology_id": ontology_id, "following": request.method != "DELETE"
    })
