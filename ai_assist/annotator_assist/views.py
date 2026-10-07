import json
import logging
import uuid

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from user_service.libs.decorators import authentication_required
from user_service.libs.safe_http import SafeRequestError, validate_public_https_url
from user_service.middlewares.request import get_username_from_request
from ai_assist.session_logging import create_session_for_user
from ai_assist.redis_client import redis_client
from ai_assist.transport import run_redis_key

from .tasks import STATUS_KEY, annotate_text_task, set_status
from .workflow import annotate_text

logger = logging.getLogger(__name__)
MAX_INPUT_BYTES = 10_000_000


@require_POST
@authentication_required
def annotate(request):
    if not settings.AI_ASSIST_ENABLED:
        return JsonResponse({"error": "Not found."}, status=404)
    if request.content_type != "multipart/form-data":
        return JsonResponse({"error": "Upload a .txt file as multipart form field 'file'."}, status=415)
    upload = request.FILES.get("file")
    if not upload or not upload.name.lower().endswith(".txt"):
        return JsonResponse({"error": "A .txt file is required in form field 'file'."}, status=400)
    if upload.size > MAX_INPUT_BYTES:
        return JsonResponse({"error": "Input must be at most 10 MB."}, status=413)
    try:
        text = upload.read(MAX_INPUT_BYTES + 1).decode("utf-8")
    except UnicodeDecodeError:
        return JsonResponse({"error": "Text file must be UTF-8."}, status=400)
    if len(text.encode("utf-8")) > MAX_INPUT_BYTES:
        return JsonResponse({"error": "Input must be at most 10 MB."}, status=413)

    webhook_url = request.headers.get("X-Webhook-URL")
    if not text.strip():
        return JsonResponse({"error": "Input text must be non-empty."}, status=400)
    if webhook_url is not None:
        if not isinstance(webhook_url, str) or len(webhook_url) > 2048:
            return JsonResponse({"error": "Invalid webhook URL."}, status=400)
        try:
            validate_public_https_url(webhook_url)
        except SafeRequestError:
            return JsonResponse({"error": "Webhook URL must be a public HTTPS URL."}, status=400)

    run_id = str(uuid.uuid4())
    create_session_for_user(run_id, get_username_from_request(), "annotator", {"size_bytes": upload.size, "filename": upload.name})
    if webhook_url:
        try:
            set_status(run_id, "queued", get_username_from_request())
            task = annotate_text_task.delay(run_id, text, webhook_url)
        except Exception:
            logger.exception("Unable to queue dataset annotation")
            return JsonResponse({"error": "Unable to queue the annotation."}, status=503)
        return JsonResponse({"run_id": run_id, "task_id": task.id, "workflow": "annotator", "status_path": f"/ai_assist/annotate/status/{run_id}/"}, status=202)

    try:
        result, complete = annotate_text(text, run_id)
    except Exception:
        logger.exception("Dataset annotation failed")
        return JsonResponse({"error": "Unable to annotate the dataset."}, status=503)
    response = JsonResponse(result, json_dumps_params={"ensure_ascii": False}, content_type="application/ld+json")
    response["X-Annotation-Status"] = "complete" if complete else "partial"
    return response


@require_GET
@authentication_required
def annotation_status(request, run_id):
    try:
        record = redis_client.get(run_redis_key(run_id, STATUS_KEY))
    except Exception:
        return JsonResponse({"error": "Status is temporarily unavailable."}, status=503)
    if not record:
        return JsonResponse({"error": "Status expired."}, status=404)
    record = json.loads(record)
    if record.get("owner") != get_username_from_request():
        return JsonResponse({"error": "Not found."}, status=404)
    return JsonResponse({"run_id": str(run_id), "status": record["status"]})
