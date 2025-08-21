from user_service.libs.decorators import (
    error_handler_decorator,
    authentication_required,
)
from user_service.libs.utils import create_json_response
from django.views.decorators.http import require_http_methods
from user_service.middlewares.request import (
    get_headers_dict,
    get_username_from_request,
    get_client_id_from_request,
)
from user.libs.auth import Auth
from user.models import UserModel, RoleModel, SearchSettingModel
from django.http import Http404
from django.views import View
import json
from jose import jwt
import datetime
from django.conf import settings


@require_http_methods(["GET"])
def ping(request):
    return create_json_response({"response": "Pong"})


@error_handler_decorator
@require_http_methods(["GET"])
def login(request):
    _time = datetime.datetime
    auth_object_dict = get_headers_dict()
    auth = Auth(**auth_object_dict)
    auth.abort_if_client_app_not_valid()
    auth.abort_if_not_auth_provider()
    auth_response_dict = auth.authenticate()
    if auth_response_dict:
        created_at = _time.now()
        updated_at = _time.now()
        user_db_dict = {
            "username": get_username_from_request(),
            "name": auth_response_dict["name"],
            "auth_provider": auth_object_dict["auth_provider"],
            "client_ts": auth_object_dict["client_ts_id"],
            "created_at": created_at,
            "updated_at": updated_at,
            "user_extra": {},
        }
        user_model = UserModel(**user_db_dict)
        user = user_model.register_user_if_not_exist()
        if isinstance(user, str):
            # user is type of string means the model returned an error instead of a user instance.
            return create_json_response({"issue": user})

        auth.user_id = user.id
        role_model = RoleModel(user=user, client_ts=auth_object_dict["client_ts_id"])
        auth_response_dict["system_admin"] = role_model.target_object_type == "system"
        auth_response_dict["settings"] = user.user_extra
        auth_response_dict["id"] = user.id
        expires = _time.now(datetime.UTC) + datetime.timedelta(24 * 60 * 7)  # a week
        auth_object_dict["exp"] = expires
        jwt_token = jwt.encode(auth_response_dict, settings.SECRET_KEY, algorithm="HS256")
        return create_json_response(jwt_token)
    return create_json_response({"issue": "auth is rejected"})


@error_handler_decorator
@require_http_methods(["GET"])
def validate_login(request):
    auth_object_dict = get_headers_dict()
    username = get_username_from_request()
    user_id = UserModel.get_user_id_by_username(username=username)
    auth_object_dict["user_id"] = user_id
    auth = Auth(**auth_object_dict)
    auth.abort_if_not_authenticated()
    return create_json_response({"valid": True})


@error_handler_decorator
@authentication_required
@require_http_methods(["POST"])
def save_settings(request):
    username = get_username_from_request()
    settings = json.loads(request.body)
    setting_is_saved = UserModel.save_user_extra(username=username, user_extra=settings)
    return create_json_response({"saved": setting_is_saved})


class SearchSettings(View):
    @error_handler_decorator
    @authentication_required
    def get(self, request, id=None):
        username = get_username_from_request()
        client_ts = get_client_id_from_request()
        user = UserModel.objects.filter(username=username, client_ts=client_ts).first()
        if id:
            setting = SearchSettingModel.objects.filter(id=id).first()
            if setting and setting.can_visit_edit(user_id=user.id):
                return create_json_response({"setting": setting.to_dict()})

            raise Http404("Setting not found")

        settings = user.search_settings.all()
        return create_json_response(
            {"settings": [setting.to_dict() for setting in settings]}
        )

    @error_handler_decorator
    @authentication_required
    def post(self, request, id=None):
        _time = datetime.datetime
        username = get_username_from_request()
        client_ts_id = get_client_id_from_request()
        payload = json.loads(request.body)
        user = UserModel.objects.filter(
            username=username, client_ts=client_ts_id
        ).first()
        search_setting_model = SearchSettingModel(
            user=user,
            title=payload["title"],
            setting=payload["setting"],
            description=payload.get("description", ""),
            created_at=_time.now(),
        )
        search_setting_model.save()
        return create_json_response({"saved": search_setting_model.to_dict()})

    @error_handler_decorator
    @authentication_required
    def delete(self, request, id):
        username = get_username_from_request()
        user_id = UserModel.get_user_id_by_username(username=username)
        setting = SearchSettingModel.objects.filter(id=id).first()
        if setting and setting.can_visit_edit(user_id=user_id):
            setting.delete()
            return create_json_response({"deleted": True})

        raise Http404("Setting not found")

    @error_handler_decorator
    @authentication_required
    def put(self, request, id):
        username = get_username_from_request()
        client_ts = get_client_id_from_request()
        payload = json.loads(request.body)
        user = UserModel.objects.filter(username=username, client_ts=client_ts).first()
        setting = SearchSettingModel.objects.filter(id=id).first()
        if setting and setting.can_visit_edit(user_id=user.id):
            setting_model = SearchSettingModel(
                user=user,
                title=payload["title"],
                setting=payload["setting"],
                description=payload.get("description", ""),
            )

            setting_model.update(id=id)
            return create_json_response({"updated": setting_model.to_dict()})
        raise Http404("Setting not found")
