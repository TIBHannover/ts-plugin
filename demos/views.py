import json
import uuid

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .redis_client import redis_client
from .tasks import run_agent_task


@require_POST
def start_agent(request):
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Request body must be valid JSON."}, status=400)

    input_text = payload.get("input", "")
    if not isinstance(input_text, str):
        return JsonResponse({"error": "'input' must be a string."}, status=400)

    run_id = str(uuid.uuid4())
    redis_client.delete(
        f"agent:{run_id}:cancel",
        f"agent:{run_id}:input",
        f"agent:{run_id}:ready",
    )
    task = run_agent_task.delay(run_id=run_id, input_text=input_text)

    return JsonResponse(
        {
            "run_id": run_id,
            "task_id": task.id,
            "websocket_path": f"/ws/demos/agent/{run_id}/",
        },
        status=202,
    )
