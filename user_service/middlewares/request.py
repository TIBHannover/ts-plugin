import threading
import secrets
from jose import jwt
from django.conf import settings
from user.models import UserModel
from django.core.exceptions import PermissionDenied
from user_service.libs.utils import make_hash

_current_context = threading.local()


class RequestMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _current_context.request = request
        response = self.get_response(request)
        return response


def get_client_id_from_request():
    request = getattr(_current_context, "request", None)
    if request:
        return request.headers.get("X-TS-Frontend-Id")
    return ""


def get_headers_dict():
    request = getattr(_current_context, "request", {"headers": {}})
    return {
        "auth_provider": request.headers.get("X-TS-Auth-Provider"),
        "orcid_id": get_orcid_id_jwt_payload(),
        "client_ts_id": request.headers.get("X-TS-Frontend-Id"),
        "code": request.headers.get("X-TS-Auth-APP-Code"),
    }


def get_request_method():
    request = getattr(_current_context, "request", None)
    if request:
        return request.method
    return ""


def get_access_token_for_stats():
    # Authorization token is not jwt format in this particular case. is directly the access token
    request = getattr(_current_context, "request", None)
    if request:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            parts = auth_header.split("Bearer ")
            return parts[1].strip()
    return "default"


def get_api_key_from_request():
    request = getattr(_current_context, "request", None)
    if request:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("apk_"):
            return auth_header
    return ""


def get_jwt_token_from_request():
    request = getattr(_current_context, "request", None)
    if not request:
        return ""
    return request.headers.get("X-Auth-Token") or request.COOKIES.get("jwt", "")


def get_orcid_id_jwt_payload():
    token = get_jwt_token_from_request()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload.get("orcid_id", "")
    except:
        return ""


def get_username_from_request():
    api_key = get_api_key_from_request()
    if api_key:
        # this is an api call
        user = UserModel.objects.filter(api_key=make_hash(api_key)).first()
        if user:
            return user.username
        else:
            raise PermissionDenied("Invalid API key")

    token = get_jwt_token_from_request()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload.get("ts_username", "")
    except:
        return ""


def is_csrf_valid():
    request = getattr(_current_context, "request", None)
    if not request:
        return False
    csrf_token = request.headers.get("X-CSRF-Token")
    if not csrf_token:
        return False
    token = get_jwt_token_from_request()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        expected_csrf_token = payload.get("csrf", "")
        if not expected_csrf_token and request.headers.get("X-Auth-Token"):
            legacy_payload = jwt.decode(
                csrf_token, settings.SECRET_KEY, algorithms=["HS256"]
            )
            return bool(legacy_payload.get("csrf", ""))
        return secrets.compare_digest(csrf_token, expected_csrf_token)
    except:
        return False
