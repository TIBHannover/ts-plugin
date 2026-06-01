import secrets

from django.core.exceptions import BadRequest
from user_service.libs.decorators import (
    error_handler_decorator,
    authentication_required,
)
from user_service.libs.utils import create_json_response
from django.views.decorators.http import require_http_methods
from user_service.middlewares.request import (
    get_headers_dict,
    get_username_from_request,
)
from user_service.middlewares.client_id import get_client_id_from_request
from user.libs.auth import Auth
from user.models import UserModel, RoleModel, SearchSettingModel
from django.http import Http404, HttpResponseServerError
from django.views import View
import json
from jose import jwt
import datetime
from django.conf import settings
import secrets
from django.http import JsonResponse
from user_service.libs.utils import make_hash
import requests
from django.core.cache import cache


@require_http_methods(["GET"])
def ping(request):
    return create_json_response({"response": "Pong"})


@error_handler_decorator
@require_http_methods(["GET"])
@authentication_required
def close_endpoint(request):
    # used for testing auth validation
    return create_json_response({"response": "closed"})


@error_handler_decorator
@require_http_methods(["GET"])
def login(request):
    _time = datetime.datetime
    auth_object_dict = get_headers_dict()
    if auth_object_dict["client_ts_id"] not in settings.CLIENT_TERMINOLOGY_SERVICES:
        return create_json_response({"issue": "unkown client id"})
    auth = Auth(**auth_object_dict)
    auth.abort_if_not_auth_provider()
    auth_response_dict = auth.authenticate()
    if auth_response_dict:
        created_at = _time.now()
        updated_at = _time.now()
        user_db_dict = {
            "username": auth_response_dict["ts_username"],
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
        auth_response_dict["exp"] = expires
        jwt_token = jwt.encode(
            auth_response_dict, settings.SECRET_KEY, algorithm="HS256"
        )

        csrf_token = jwt.encode(
            {"csrf": secrets.token_urlsafe(32)},
            settings.SECRET_KEY,
            algorithm="HS256",
        )
        auth_response_dict["csrf_token"] = csrf_token
        # remove the token from the payload since jwt already has it
        auth_response_dict.pop("token", None)
        auth_response_dict["jwt"] = jwt_token
        response = JsonResponse({"_result": auth_response_dict})
        return response
    return create_json_response({"issue": "auth is rejected"})


@error_handler_decorator
@require_http_methods(["GET"])
def login_with_device_flow(request):
    client_id = settings.DEFAULT_GITHUB_CLIENT_ID
    SCOPES = "user public_repo"
    response = requests.post(
        "https://github.com/login/device/code",
        headers={"Accept": "application/json"},
        data={
            "client_id": client_id,
            "scope": SCOPES,
        },
        timeout=10,
    )
    print(response.text)
    print(response.json())
    response.raise_for_status()
    response = response.json()
    cache.set(
        f"github_device:{response['device_code']}",
        {
            "interval": response.get("interval", 5),
            "last_poll": 0,
        },
        timeout=300,
    )
    return create_json_response(
        {"code": response["user_code"], "device_code": response["device_code"]}
    )


@error_handler_decorator
@require_http_methods(["POST"])
def send_term_request(request):
    payload = json.loads(request.body)
    device_code = payload["device_code"]
    state = cache.get(f"github_device:{device_code}")
    if not state:
        raise BadRequest("Invalid device code")

    now = datetime.datetime.now()
    interval = state["interval"]
    if state["last_poll"] == 0:
        state["last_poll"] = now
    elif now - state["last_poll"] < datetime.timedelta(seconds=interval):
        return create_json_response({"status": "pending"})

    state["last_poll"] = now
    cache.set(f"github_device:{device_code}", state, timeout=300)

    response = requests.post(
        "https://github.com/login/oauth/access_token",
        headers={"Accept": "application/json"},
        data={
            "client_id": settings.DEFAULT_GITHUB_CLIENT_ID,
            "device_code": device_code,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        },
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    if "access_token" in data:
        token = data["access_token"]
        payload["repo_url"] = (
            "https://api.github.com/repos/TIBHannover/VibrationalSpectroscopyOntology/issues"
        )
        createed_issue_url = submit_term_request(payload, token)
        if not createed_issue_url:
            return create_json_response({"status": "denied"})
        cache.delete(f"github_device:{device_code}")
        return create_json_response(
            {"status": "success", "issue_url": createed_issue_url}
        )

    error = data.get("error")
    if error == "authorization_pending":
        return create_json_response({"status": "pending"})

    if error == "slow_down":
        state["interval"] += 5
        cache.set(f"github_device:{device_code}", state, timeout=300)
        return create_json_response({"status": "slow_down"})

    if error == "expired_token" or error == "access_denied":
        cache.delete(f"github_device:{device_code}")
        return create_json_response({"status": "denied"})

    return create_json_response({"status": "denied for unknown reason"})


def submit_term_request(form_data, token):
    issue_title = form_data["title"]
    issue_content = form_data["content"]
    issue_creator_url = form_data["repo_url"]
    payload = {"title": issue_title, "body": issue_content}
    headers = {
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    resp = requests.post(issue_creator_url, json=payload, headers=headers)
    if resp.status_code == 201:
        json_result = resp.json()
        new_issue_url = json_result.get("html_url")
        return new_issue_url

    return None


@error_handler_decorator
@authentication_required
@require_http_methods(["GET"])
def logout(request):
    response = JsonResponse({"_result": "logged out"})
    response.delete_cookie("jwt")
    return response


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
def create_api_key(request):
    payload = json.loads(request.body)
    username = get_username_from_request()
    user = UserModel.get_by_username(username=username)
    token = secrets.token_hex(32)
    token = "apk_" + user.client_ts + "_" + token
    api_key_user = {
        "username": "api_" + secrets.token_urlsafe(32),
        "name": payload.get("name", user.name),
        "auth_provider": "apikey",
        "client_ts": user.client_ts,
        "created_at": datetime.datetime.now(),
        "description": payload.get("description", ""),
        "title": payload["title"],
        "api_key": make_hash(token),
        "expires_at": payload.get("expires_at", None),
        "owner": user,
    }
    api_key_user = UserModel(**api_key_user)
    api_key_user.save()
    if not api_key_user.id:
        return HttpResponseServerError("Something went wrong.")

    return create_json_response({"token": token, "api_key": api_key_user.to_dict()})


@error_handler_decorator
@authentication_required
@require_http_methods(["PUT"])
def update_api_key(request):
    payload = json.loads(request.body)
    username = get_username_from_request()
    user = UserModel.get_by_username(username=username)
    api_key_id = payload["id"]
    api_key = UserModel.objects.filter(id=api_key_id).first()
    if not api_key:
        raise Http404("API key does not exist.")
    if api_key.owner.id != user.id:
        raise Http404("Not authorized")
    api_key.name = payload.get("name", user.name)
    api_key.description = payload.get("description", "")
    api_key.expires_at = payload.get("expires_at", None)
    api_key.title = payload["title"]
    api_key.save()
    return create_json_response({"updated": api_key.to_dict()})


@error_handler_decorator
@authentication_required
@require_http_methods(["DELETE"])
def delete_api_key(request):
    payload = json.loads(request.body)
    username = get_username_from_request()
    user = UserModel.get_by_username(username=username)
    api_key_id = payload["id"]
    api_key = UserModel.objects.filter(id=api_key_id).first()
    if not api_key:
        raise Http404("API key does not exist.")
    if api_key.owner.id != user.id:
        raise Http404("Not authorized")
    api_key.delete()
    return create_json_response({"deleted": True})


@error_handler_decorator
@authentication_required
@require_http_methods(["GET"])
def get_api_keys(request):
    username = get_username_from_request()
    user = UserModel.get_by_username(username=username)
    api_keys = UserModel.objects.filter(owner=user).all()
    return create_json_response(
        {"api_keys": [api_key.to_dict() for api_key in api_keys]}
    )


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
