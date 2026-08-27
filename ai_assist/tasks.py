import json

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.conf import settings

from ai_assist.agents import run_agent
from ai_assist.prompts import PROMPT
from ai_assist.vars import (
    CHANNEL_EVENT_TYPE_AGENT_EVENT,
    READY_WAIT_TIMEOUT_SECONDS,
    REDIS_TRUE_VALUE,
    RUN_REDIS_KEY_AWAITING_INPUT,
    RUN_REDIS_KEY_AWAITING_REJECTION,
    RUN_REDIS_KEY_CANCEL,
    RUN_REDIS_KEY_INPUT,
    RUN_REDIS_KEY_READY,
    RUN_REDIS_KEY_REJECTIONS,
    RUN_REDIS_KEY_STATE,
    RUN_REDIS_KEYS,
    RUN_TTL_SECONDS,
    SERVER_MESSAGE_TYPE_AGENT_STARTED,
    SERVER_MESSAGE_TYPE_CANCELLED,
    SERVER_MESSAGE_TYPE_DONE,
    SERVER_MESSAGE_TYPE_ERROR,
    SERVER_MESSAGE_TYPE_PROGRESS,
    SERVER_MESSAGE_TYPE_QUESTION,
    run_group_name,
    run_redis_key,
)

from .redis_client import redis_client

AGENT_MAX_LOOPS = settings.TERM_REQUEST_AI_ASSIST_MAX_LOOPS
AGENT_MAX_REJECTIONS = settings.TERM_REQUEST_AI_ASSIST_MAX_REJECTIONS


@shared_task
def run_agent_task(run_id, input_text):
    try:
        if not redis_client.blpop(
            run_redis_key(run_id, RUN_REDIS_KEY_READY),
            timeout=READY_WAIT_TIMEOUT_SECONDS,
        ):
            cleanup_run(run_id)
            return
        state = {
            "messages": [
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": input_text},
            ],
            "response": new_response(),
            "steps": 0,
        }
        emit(
            {
                "type": SERVER_MESSAGE_TYPE_AGENT_STARTED,
                "run_id": run_id,
                "input": input_text,
            },
            run_id,
        )
        run_conversation(run_id, state)
    except Exception:
        fail_run(run_id)


@shared_task
def resume_agent_task(run_id):
    try:
        state_json = redis_client.get(run_redis_key(run_id, RUN_REDIS_KEY_STATE))
        if not state_json:
            return
        rejection_count = int(
            redis_client.get(run_redis_key(run_id, RUN_REDIS_KEY_REJECTIONS)) or 0
        )
        if rejection_count > AGENT_MAX_REJECTIONS:
            emit_no_parent_found(run_id)
            cleanup_run(run_id)
            return
        state = json.loads(state_json)
        if rejection_count > state.get("retry_started", 0):
            state["steps"] = 0
            state["retry_started"] = rejection_count
            state["response"]["search_call_count"] = 0
        state["response"]["needs_user_input"] = False
        state["response"]["question"] = ""
        state["response"]["is_final"] = False
        run_conversation(run_id, state)
    except Exception:
        fail_run(run_id)


def new_response():
    return {
        "parent_label": "",
        "ontology": "",
        "parent_iri": "",
        "error": None,
        "is_final": False,
        "usage_stats": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "search_call_count": 0,
        "progress_feedback": "",
        "needs_user_input": False,
        "question": "",
    }


def run_conversation(run_id, state):
    try:
        response = state["response"]
        messages = state["messages"]
        for step in range(state["steps"], AGENT_MAX_LOOPS):
            if is_cancelled(run_id):
                cleanup_run(run_id)
                return

            add_pending_user_input(messages, run_id)
            run_agent(messages, response)
            state["steps"] = step + 1

            if response["needs_user_input"]:
                save_state(run_id, state)
                emit(
                    {
                        "type": SERVER_MESSAGE_TYPE_QUESTION,
                        "message": response["question"],
                    },
                    run_id,
                )
                return

            if response["is_final"]:
                save_state(run_id, state, RUN_REDIS_KEY_AWAITING_REJECTION)
                emit_done(response, run_id)
                return

            if response["progress_feedback"]:
                emit(
                    {
                        "type": SERVER_MESSAGE_TYPE_PROGRESS,
                        "message": response["progress_feedback"],
                    },
                    run_id,
                )

        emit(
            {
                "type": SERVER_MESSAGE_TYPE_ERROR,
                "message": f"Agent reached the {AGENT_MAX_LOOPS}-step limit without a final response.",
            },
            run_id,
        )
        cleanup_run(run_id)
    except Exception:
        fail_run(run_id)


def save_state(run_id, state, awaiting_key=RUN_REDIS_KEY_AWAITING_INPUT):
    redis_client.setex(
        run_redis_key(run_id, RUN_REDIS_KEY_STATE), RUN_TTL_SECONDS, json.dumps(state)
    )
    redis_client.setex(
        run_redis_key(run_id, awaiting_key), RUN_TTL_SECONDS, REDIS_TRUE_VALUE
    )


def emit_done(response, run_id):
    emit(
        {
            "type": SERVER_MESSAGE_TYPE_DONE,
            "parent_label": response.get("parent_label", "N/A"),
            "ontology": response.get("ontology", "N/A"),
            "parent_iri": response.get("parent_iri", "N/A"),
            "error": response.get("error", ""),
        },
        run_id,
    )


def emit_no_parent_found(run_id):
    emit(
        {
            "type": SERVER_MESSAGE_TYPE_DONE,
            "parent_label": "",
            "ontology": "",
            "parent_iri": "",
            "error": f"Unable to find a suitable parent term after {AGENT_MAX_REJECTIONS + 1} rejected recommendations.",
        },
        run_id,
    )


def emit(payload, run_id):
    """Deliver a worker event to the Channels group holding the client socket."""
    async_to_sync(get_channel_layer().group_send)(
        run_group_name(run_id),
        {"type": CHANNEL_EVENT_TYPE_AGENT_EVENT, "payload": payload},
    )


def is_cancelled(run_id):
    if (
        redis_client.get(run_redis_key(run_id, RUN_REDIS_KEY_CANCEL))
        != REDIS_TRUE_VALUE
    ):
        return False
    emit({"type": SERVER_MESSAGE_TYPE_CANCELLED, "run_id": run_id}, run_id)
    return True


def add_pending_user_input(messages, run_id):
    """Drain queued feedback in FIFO order before the assistant's next LLM turn."""
    while message := redis_client.lpop(run_redis_key(run_id, RUN_REDIS_KEY_INPUT)):
        messages.append({"role": "user", "content": message})


def cleanup_run(run_id):
    """Remove the Redis data associated with a completed or failed run."""
    redis_client.delete(*(run_redis_key(run_id, key) for key in RUN_REDIS_KEYS))


def fail_run(run_id):
    """Notify the client about an unexpected failure and release all run state."""
    try:
        emit(
            {"type": SERVER_MESSAGE_TYPE_ERROR, "message": "Assistant run failed."},
            run_id,
        )
    finally:
        cleanup_run(run_id)
