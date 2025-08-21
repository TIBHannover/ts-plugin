import threading
from jose import jwt, JWTError
from django.conf import settings

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
    request = getattr(_current_context, "request", {'headers': {}})
    return {
        "auth_provider": request.headers.get("X-TS-Auth-Provider"),
        "orcid_id": get_orcid_id_jwt_payload(),
        "client_ts_id": request.headers.get("X-TS-Frontend-Id"),
        "client_ts_token": request.headers.get("X-TS-Frontend-Token"),
        "code": request.headers.get("X-TS-Auth-APP-Code"),
    }


def get_request_method():
    request = getattr(_current_context, "request", None)
    if request:
        return request.method
    return ""


def get_jwt_token_from_request():
    request = getattr(_current_context, "request", None)
    auth_header = request.headers.get("Authorization", "not_exist")
    if "Bearer" not in auth_header:
        return ""
    return auth_header.split("Bearer ")[1]


def get_orcid_id_jwt_payload():
    token = get_jwt_token_from_request()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload.get("orcid_id", "")
    except JWTError:
        return ""


def get_username_from_request():
    token = get_jwt_token_from_request()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload.get("ts_username", "")
    except JWTError:
        return ""
