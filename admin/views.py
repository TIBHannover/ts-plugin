from user.models import UserModel, RoleModel
from user_service.libs.decorators import (
    error_handler_decorator,
    authentication_required,
)
from django.views.decorators.http import require_http_methods
from user_service.middlewares.request import (
    get_headers_dict,
    get_username_from_request,
)
from user_service.middlewares.client_id import get_client_id_from_request
import json
from user_service.libs.utils import create_json_response
from user_service.middlewares.request import get_access_token_for_stats
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST
from django.http import HttpResponse
from admin.stats import Stats


@error_handler_decorator
@authentication_required
@require_http_methods(["POST"])
def is_entity_admin(request):
    auth_object_dict = get_headers_dict()
    user = UserModel.get_by_username(username=get_username_from_request())
    auth_object_dict["user_id"] = user.id
    _form = json.loads(request.body)
    ontologyId = _form.get("ontologyId")
    collectionId = _form.get("collectionId")

    for key, value in user.get_user_admin_roles().items():
        if ontologyId in value:
            return create_json_response({"is_admin": True})
        if collectionId in value:
            return create_json_response({"is_admin": True})
        if key == "system" and len(value) > 0:
            return create_json_response({"is_admin": True})

    return create_json_response({"is_admin": False})


@error_handler_decorator
@authentication_required
@require_http_methods(["POST"])
def is_system_admin():
    client_ts = get_client_id_from_request()
    user = UserModel.objects.filter(
        username=get_username_from_request(), client_ts=client_ts
    ).first()

    role_model = RoleModel.objects.filter(user=user, client_ts=client_ts).first()
    is_admin = True if role_model.target_object_type == "system" else False
    return create_json_response({"is_system_admin": is_admin})


@error_handler_decorator
@require_http_methods(["GET"])
def metrics(request):
    stats = Stats()
    stats.run()
    return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)
