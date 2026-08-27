import json
import secrets
import uuid

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from user_service.libs.decorators import authentication_required

from .agents import build_user_prompt
from .redis_client import redis_client
from .tasks import run_agent_task
from .vars import (
    CATEGORIES,
    RUN_REDIS_KEY_CANCEL,
    RUN_REDIS_KEY_INPUT,
    RUN_REDIS_KEY_READY,
    RUN_REDIS_KEY_SOCKET_TOKEN,
    RUN_TTL_SECONDS,
    WEBSOCKET_PATH_TEMPLATE,
    WEBSOCKET_TOKEN_BYTES,
    run_redis_key,
)


@require_POST
@authentication_required
def start_agent(request):
    """Start one bounded assistant run and return its WebSocket address."""
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Request body must be valid JSON."}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"error": "Request body must be a JSON object."}, status=400)

    label = payload.get("label")
    description = payload.get("description")
    category = payload.get("category")
    if not all(isinstance(value, str) and value.strip() for value in (label, description, category)):
        return JsonResponse(
            {"error": "'label', 'description', and 'category' must be non-empty strings."},
            status=400,
        )
    if (
        len(label) > settings.TERM_REQUEST_INPUT_MAX_LENGTH
        or len(description) > settings.TERM_REQUEST_INPUT_MAX_LENGTH
    ):
        return JsonResponse(
            {
                "error": "'label' and 'description' must be at most "
                f"{settings.TERM_REQUEST_INPUT_MAX_LENGTH} characters."
            },
            status=400,
        )
    category = next((key for key in CATEGORIES if key.casefold() == category.casefold()), None)
    if category is None:
        return JsonResponse({"error": "'category' is not supported."}, status=400)

    category_text = f"{category}:{','.join(CATEGORIES[category])}"
    input_text = build_user_prompt(label, description, category_text)

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
        task = run_agent_task.delay(run_id=run_id, input_text=input_text)
    except Exception:
        rollback_run_start(run_id)
        return JsonResponse({"error": "Unable to start the assistant."}, status=503)

    return JsonResponse(
        {
            "run_id": run_id,
            "task_id": task.id,
            "websocket_path": WEBSOCKET_PATH_TEMPLATE.format(run_id=run_id),
            "websocket_token": websocket_token,
        },
        status=202,
    )


def rollback_run_start(run_id):
    """Release a partially-created run when task enqueueing fails."""
    redis_client.delete(
        run_redis_key(run_id, RUN_REDIS_KEY_CANCEL),
        run_redis_key(run_id, RUN_REDIS_KEY_INPUT),
        run_redis_key(run_id, RUN_REDIS_KEY_READY),
        run_redis_key(run_id, RUN_REDIS_KEY_SOCKET_TOKEN),
    )
