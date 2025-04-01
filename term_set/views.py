from user_service.libs.utils import create_json_response
from django.views.decorators.http import require_http_methods



@require_http_methods(["GET"])
def ping(request):
    return create_json_response({"response": "Pong"})


