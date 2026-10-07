import json
import logging

from celery import shared_task

from user_service.libs.safe_http import safe_post
from ai_assist.redis_client import redis_client
from ai_assist.transport import run_redis_key

STATUS_KEY = "annotator_status"
STATUS_TTL_SECONDS = 24 * 3600
logger = logging.getLogger(__name__)


def set_status(run_id, status, owner=None):
    key = run_redis_key(run_id, STATUS_KEY)
    record = json.loads(redis_client.get(key) or b"{}")
    record["status"] = status
    if owner is not None:
        record["owner"] = owner
    redis_client.setex(key, STATUS_TTL_SECONDS, json.dumps(record))


def update_status(run_id, status):
    try:
        set_status(run_id, status)
    except Exception:
        logger.exception("Unable to update annotation status for %s", run_id)


@shared_task
def annotate_text_task(run_id, text, webhook_url):
    from .workflow import annotate_text

    update_status(run_id, "running")
    try:
        result, complete = annotate_text(text, run_id)
        status = "complete" if complete else "partial"
    except Exception:
        logger.exception("Dataset annotation failed for %s", run_id)
        result = {"run_id": run_id, "status": "failed", "error": "Unable to annotate the dataset."}
        status = "failed"
    update_status(run_id, "delivering" if status != "failed" else "annotation_failed")
    try:
        deliver_annotation_task.delay(run_id, result, webhook_url, status)
    except Exception:
        update_status(run_id, "delivery_failed")
        raise
    return {"run_id": run_id, "status": status}


@shared_task(bind=True, max_retries=5)
def deliver_annotation_task(self, run_id, result, webhook_url, status):
    try:
        response = safe_post(
            webhook_url,
            json.dumps(result, ensure_ascii=False).encode("utf-8"),
            content_type="application/ld+json" if status != "failed" else "application/json",
            headers={"X-Run-ID": run_id, "X-Idempotency-Key": run_id, "X-Annotation-Status": status},
        )
        if not 200 <= response.status_code < 300:
            raise RuntimeError("Annotation webhook rejected the result.")
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            update_status(run_id, "delivery_failed")
            raise
        raise self.retry(exc=exc, countdown=min(60 * 2 ** self.request.retries, 3600))
    update_status(run_id, "annotation_failed_delivered" if status == "failed" else "partial_delivered" if status == "partial" else "delivered")
    return {"run_id": run_id, "status": status}
