import json
import secrets
import uuid

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from user_service.libs.decorators import authentication_required
from user_service.middlewares.request import get_username_from_request

from .agent import build_search_agent_input, build_term_request_agent_input
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
from .state import (
    CATEGORIES,
)


@require_POST
@authentication_required
def start_agent(request):
    """Backward-compatible term-request entry point."""
    return start_workflow(request, "term_request", include_workflow=False)


@require_POST
@authentication_required
def start_term_request(request):
    return start_workflow(request, "term_request")


@require_POST
@authentication_required
def start_search(request):
    return start_workflow(request, "search")


def start_workflow(request, workflow, include_workflow=True):
    """Start one bounded assistant workflow and return its WebSocket address."""
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
        return JsonResponse(
            {"error": "'description' must be a non-empty string."},
            status=400,
        )
    if len(description) > settings.TERM_REQUEST_INPUT_MAX_LENGTH:
        return JsonResponse(
            {"error": f"'description' must be at most {settings.TERM_REQUEST_INPUT_MAX_LENGTH} characters."},
            status=400,
        )
    search_inputs = None
    if workflow == "search":
        input_text = build_search_agent_input(description)
    else:
        label = payload.get("label")
        category = payload.get("category")
        domain = payload.get("domain", "")
        if not all(isinstance(value, str) and value.strip() for value in (label, category)):
            return JsonResponse(
                {"error": "'label', 'description', and 'category' must be non-empty strings."},
                status=400,
            )
        if len(label) > settings.TERM_REQUEST_INPUT_MAX_LENGTH:
            return JsonResponse(
                {"error": f"'label' must be at most {settings.TERM_REQUEST_INPUT_MAX_LENGTH} characters."},
                status=400,
            )
        if not isinstance(domain, str) or len(domain) > settings.TERM_REQUEST_INPUT_MAX_LENGTH:
            return JsonResponse(
                {
                    "error": f"'domain' must be a string of at most {settings.TERM_REQUEST_INPUT_MAX_LENGTH} characters."
                },
                status=400,
            )
        category = next((key for key in CATEGORIES if key.casefold() == category.casefold()), None)
        if category is None:
            return JsonResponse({"error": "'category' is not supported."}, status=400)
        input_text = build_term_request_agent_input(
            label,
            description,
            f"{category}:{','.join(CATEGORIES[category])}",
            domain.strip(),
        )
        search_inputs = [
            build_search_agent_input(label.strip()),
            build_search_agent_input(description.strip()),
        ]

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
        task_kwargs = {"run_id": run_id, "input_text": input_text}
        if include_workflow:
            task_kwargs["workflow"] = workflow
        if search_inputs:
            task_kwargs["search_inputs"] = search_inputs
        task = run_agent_task.delay(**task_kwargs)
    except Exception:
        rollback_run_start(run_id)
        return JsonResponse({"error": "Unable to start the assistant."}, status=503)

    create_session_for_user(
        run_id, get_username_from_request(), workflow, payload
    )

    return JsonResponse(
        {
            "run_id": run_id,
            "task_id": task.id,
            "websocket_path": WEBSOCKET_PATH_TEMPLATE.format(run_id=run_id),
            "websocket_token": websocket_token,
            "workflow": workflow,
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
