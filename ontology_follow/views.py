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
@require_http_methods(["GET", "POST", "DELETE"])
def follows(request):
    user = UserModel.get_by_username(get_username_from_request())
    if not user:
        raise PermissionDenied("Not Authorized")
    if request.method == "GET":
        return create_json_response({
            "ontology_ids": list(user.ontology_follows.order_by("ontology_id").values_list(
                "ontology_id", flat=True
            ))
        })
    try:
        payload = json.loads(request.body)
    except ValueError:
        raise BadRequest("Invalid JSON body")
    ontology_id = payload.get("ontology_id") if isinstance(payload, dict) else None
    if not isinstance(ontology_id, str) or not ontology_id.strip():
        raise BadRequest("ontology_id must be a non-empty string")
    ontology_id = ontology_id.strip().lower()
    if request.method == "POST":
        OntologyFollowModel.objects.get_or_create(user=user, ontology_id=ontology_id)
    else:
        user.ontology_follows.filter(ontology_id=ontology_id).delete()
    return create_json_response({
        "ontology_id": ontology_id, "following": request.method == "POST"
    })
