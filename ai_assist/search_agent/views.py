import json
import secrets
import uuid

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from user_service.libs.decorators import authentication_required

from ai_assist.redis_client import redis_client
from ai_assist.session_logging import create_session_for_user
from ai_assist.tasks import run_agent_task
from ai_assist.transport import (
    RUN_REDIS_KEY_CANCEL,
    RUN_REDIS_KEY_INPUT,
    RUN_REDIS_KEY_READY,
    RUN_REDIS_KEY_SOCKET_TOKEN,
    RUN_TTL_SECONDS,
    WEBSOCKET_PATH_TEMPLATE,
    WEBSOCKET_TOKEN_BYTES,
    run_redis_key,
)
from user_service.middlewares.request import get_username_from_request

from .agent import build_input


@require_POST
@authentication_required
def start_search(request):
    if not settings.AI_ASSIST_ENABLED:
        return JsonResponse({"error": "Not found."}, status=404)
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Request body must be valid JSON."}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"error": "Request body must be a JSON object."}, status=400)
    description = payload.get("description")
    if not isinstance(description, str) or not description.strip():
        return JsonResponse({"error": "'description' must be a non-empty string."}, status=400)
    if len(description) > settings.TERM_REQUEST_INPUT_MAX_LENGTH:
        return JsonResponse(
            {"error": f"'description' must be at most {settings.TERM_REQUEST_INPUT_MAX_LENGTH} characters."},
            status=400,
        )

    run_id = str(uuid.uuid4())
    websocket_token = secrets.token_urlsafe(WEBSOCKET_TOKEN_BYTES)
    try:
        redis_client.delete(
            run_redis_key(run_id, RUN_REDIS_KEY_CANCEL),
            run_redis_key(run_id, RUN_REDIS_KEY_INPUT),
            run_redis_key(run_id, RUN_REDIS_KEY_READY),
        )
        redis_client.setex(
            run_redis_key(run_id, RUN_REDIS_KEY_SOCKET_TOKEN),
            RUN_TTL_SECONDS,
            websocket_token,
        )
        task = run_agent_task.delay(
            run_id=run_id,
            input_text=build_input(description),
            workflow="search",
        )
    except Exception:
        redis_client.delete(
            run_redis_key(run_id, RUN_REDIS_KEY_CANCEL),
            run_redis_key(run_id, RUN_REDIS_KEY_INPUT),
            run_redis_key(run_id, RUN_REDIS_KEY_READY),
            run_redis_key(run_id, RUN_REDIS_KEY_SOCKET_TOKEN),
        )
        return JsonResponse({"error": "Unable to start the assistant."}, status=503)

    create_session_for_user(run_id, get_username_from_request(), "search", payload)
    return JsonResponse(
        {
            "run_id": run_id,
            "task_id": task.id,
            "websocket_path": WEBSOCKET_PATH_TEMPLATE.format(run_id=run_id),
            "websocket_token": websocket_token,
            "workflow": "search",
        },
        status=202,
    )
