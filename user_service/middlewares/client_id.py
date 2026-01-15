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
    api_key = request.headers.get("Authorization")
    if api_key and api_key.startswith("apk_"):
        # this is an api call. the client ts id is embedded in the api key
        return api_key.split("_")[1]
    if request:
        return request.headers.get("X-TS-Frontend-Id")
    return ""
