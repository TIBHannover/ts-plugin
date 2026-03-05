from django.views.decorators.http import require_http_methods
from user_service.libs.utils import create_json_response


@require_http_methods(["GET"])
def ping(request):
    return create_json_response({"response": "Pong"})
