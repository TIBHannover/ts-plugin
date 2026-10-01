import json
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings

from .state import (
    RUN_REDIS_KEYS,
    RUN_REDIS_KEY_AWAITING_REJECTION,
    RUN_REDIS_KEY_SEARCH_AGENT_REJECTIONS,
    SERVER_MESSAGE_TYPE_AGENT_STARTED,
    SERVER_MESSAGE_TYPE_CANCELLED,
    SERVER_MESSAGE_TYPE_DONE,
    SERVER_MESSAGE_TYPE_PROGRESS,
    new_response,
    normalize_state,
)
from ai_assist.redis_client import redis_client
from ai_assist.transport import (
    CHANNEL_EVENT_TYPE_AGENT_EVENT,
    READY_WAIT_TIMEOUT_SECONDS,
    REDIS_TRUE_VALUE,
    RUN_REDIS_KEY_CANCEL,
    RUN_REDIS_KEY_READY,
    RUN_REDIS_KEY_STATE,
    RUN_TTL_SECONDS,
    SERVER_MESSAGE_TYPE_ERROR,
    run_group_name,
    run_redis_key,
)

from .agent import run_agent_turn
from .prompts import SEARCH_AGENT_PROMPT

logger = logging.getLogger(__name__)


def run_search_agent(run_id, input_text):
    try:
        if not redis_client.blpop(run_redis_key(run_id, RUN_REDIS_KEY_READY), timeout=READY_WAIT_TIMEOUT_SECONDS):
            cleanup_run(run_id)
            return
        state = {
            "messages": [{"role": "system", "content": SEARCH_AGENT_PROMPT}, {"role": "user", "content": input_text}],
            "response": new_response(),
            "steps": 0,
            "workflow": "search",
            "input_text": input_text,
        }
        emit({"type": SERVER_MESSAGE_TYPE_AGENT_STARTED, "run_id": run_id, "input": input_text}, run_id)
        run_conversation(run_id, state)
    except Exception:
        logger.exception("Unable to start search run %s", run_id)
        fail_run(run_id)


def resume_search_agent(run_id):
    try:
        state_json = redis_client.get(run_redis_key(run_id, RUN_REDIS_KEY_STATE))
        if not state_json:
            return
        state = normalize_state(json.loads(state_json))
        rejection_count = int(redis_client.get(run_redis_key(run_id, RUN_REDIS_KEY_SEARCH_AGENT_REJECTIONS)) or 0)
        if rejection_count > settings.TERM_REQUEST_AI_ASSIST_MAX_REJECTIONS:
            emit_no_candidates_found(run_id)
            cleanup_run(run_id)
            return
        if rejection_count > state.get("retry_started", 0):
            state["steps"] = 0
            state["retry_started"] = rejection_count
            response = state["response"]
            response["search_call_count"] = 0
            response["successful_search_count"] = 0
            response["excluded_search_candidates"].extend(
                {"ontologyId": candidate["ontologyId"], "iri": candidate["iri"]}
                for candidate in response["candidates"]
            )
            response["search_results"] = []
            response["candidates"] = []
        state["response"]["is_final"] = False
        run_conversation(run_id, state)
    except Exception:
        logger.exception("Unable to resume search run %s", run_id)
        fail_run(run_id)


def run_conversation(run_id, state):
    response = state["response"]
    try:
        for step in range(state["steps"], settings.SEARCH_AI_ASSIST_MAX_LOOPS):
            if is_cancelled(run_id):
                cleanup_run(run_id)
                return
            run_agent_turn(state["messages"], response, run_id, lambda message: emit({"type": SERVER_MESSAGE_TYPE_PROGRESS, "message": message}, run_id))
            state["steps"] = step + 1
            if response["is_final"]:
                save_state(run_id, state)
                emit_done(response, run_id)
                return
            for message in response.get("progress_feedbacks", []):
                emit({"type": SERVER_MESSAGE_TYPE_PROGRESS, "message": message}, run_id)
        emit({"type": SERVER_MESSAGE_TYPE_ERROR, "message": f"Agent reached the {settings.SEARCH_AI_ASSIST_MAX_LOOPS}-step limit without a final response."}, run_id)
        cleanup_run(run_id)
    except Exception:
        logger.exception("Search conversation failed for run %s", run_id)
        fail_run(run_id)


def save_state(run_id, state):
    redis_client.setex(run_redis_key(run_id, RUN_REDIS_KEY_STATE), RUN_TTL_SECONDS, json.dumps(state))
    redis_client.setex(run_redis_key(run_id, RUN_REDIS_KEY_AWAITING_REJECTION), RUN_TTL_SECONDS, "search")


def emit_done(response, run_id):
    emit({"type": SERVER_MESSAGE_TYPE_DONE, "candidates": response.get("candidates", []), "error": response.get("error", "")}, run_id)


def emit_no_candidates_found(run_id):
    rejection_limit = settings.TERM_REQUEST_AI_ASSIST_MAX_REJECTIONS + 1
    emit(
        {
            "type": SERVER_MESSAGE_TYPE_DONE,
            "candidates": [],
            "error": f"Unable to find a matching term after {rejection_limit} rejected recommendations.",
        },
        run_id,
    )


def emit(payload, run_id):
    async_to_sync(get_channel_layer().group_send)(run_group_name(run_id), {"type": CHANNEL_EVENT_TYPE_AGENT_EVENT, "payload": payload})


def is_cancelled(run_id):
    if redis_client.get(run_redis_key(run_id, RUN_REDIS_KEY_CANCEL)) != REDIS_TRUE_VALUE:
        return False
    emit({"type": SERVER_MESSAGE_TYPE_CANCELLED, "run_id": run_id}, run_id)
    return True


def cleanup_run(run_id):
    redis_client.delete(*(run_redis_key(run_id, key) for key in RUN_REDIS_KEYS))


def fail_run(run_id):
    try:
        emit({"type": SERVER_MESSAGE_TYPE_ERROR, "message": "Assistant run failed."}, run_id)
    finally:
        cleanup_run(run_id)
