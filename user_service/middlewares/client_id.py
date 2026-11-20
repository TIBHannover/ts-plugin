import threading

_current_context = threading.local()


class ClientIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _current_context.request = request
        response = self.get_response(request)
        return response


def get_client_id_from_request():
    request = getattr(_current_context, "request", None)
    if not request:
        return ""
    api_key = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if api_key.startswith("apk_"):
        # X-TS-Frontend-Id is no longer used for API-key calls.
        return api_key.split("_", 2)[1]
    return request.headers.get("X-TS-Frontend-Id")
