import threading

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
    request = getattr(_current_context, "request", {'headers':{}})
    return {
        "access_token": request.headers.get("Authorization"),
        "auth_provider": request.headers.get("X-TS-Auth-Provider"),
        "orcid_id": request.headers.get("X-TS-Orcid-Id"),
        "client_ts_id": request.headers.get("X-TS-Frontend-Id"),
        "client_ts_token": request.headers.get("X-TS-Frontend-Token"),
        "user_token": request.headers.get("X-TS-User-Token"),
        "code": request.headers.get("X-TS-Auth-APP-Code"),
        "username": request.headers.get("X-TS-User-Name"),
    }

def get_request_method():
    request = getattr(_current_context, "request", None)
    if request:
        return request.method 
    return ""


def get_username_from_request():
    request = getattr(_current_context, "request", None)
    if request:
        return request.headers.get("X-TS-User-Name")
    return ""
