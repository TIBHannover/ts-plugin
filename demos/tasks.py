from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer

from .redis_client import redis_client
from demos.vars import PROMPT
from demos.agents import run_agent

AGENT_MAX_LOOPS = 40


@shared_task
def run_agent_task(run_id, input_text):
    group_name = f"agent_run_{run_id}"
    channel_layer = get_channel_layer()
    messages = [
        {
            "role": "system",
            "content": PROMPT,
        },
        {
            "role": "user",
            "content": input_text,
        },
    ]
    usage_totals = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }

    response = {
        "parent_label": "",
        "ontology": "",
        "parent_iri": "",
        "error": None,
        "is_final": False,
        "usage_stats": usage_totals,
        "search_call_count": 0,
        "progress_feedback": "",
    }
    try:
        redis_client.blpop(f"agent:{run_id}:ready", timeout=30)

        emit(
            {
                "type": "agent_started",
                "run_id": run_id,
                "input": input_text,
            },
            channel_layer,
            group_name,
        )

        for step in range(AGENT_MAX_LOOPS):
            if is_cancelled(run_id, channel_layer, group_name):
                return

            emit(
                {
                    "type": "progress",
                    "step": step + 1,
                    "total": AGENT_MAX_LOOPS,
                    "message": f"Running step {step + 1}",
                },
                channel_layer,
                group_name,
            )

            run_agent(messages, response)

            if not response["is_final"]:
                emit(
                    {
                        "type": "progress",
                        "message": response["progress_feedback"],
                    },
                    channel_layer,
                    group_name,
                )
            else:
                break

        emit(
            {
                "type": "done",
                "parent_label": response.get("parent_label", "N/A"),
                "ontology": response.get("ontology", "N/A"),
                "parent_iri": response.get("parent_iri", "N/A"),
                "error": response.get("error", ""),
            },
            channel_layer,
            group_name,
        )

    except Exception as exc:
        emit(
            {
                "type": "error",
                "message": str(exc),
            },
            channel_layer,
            group_name,
        )

    finally:
        redis_client.delete(f"agent:{run_id}:cancel")
        redis_client.delete(f"agent:{run_id}:input")
        redis_client.delete(f"agent:{run_id}:ready")


def emit(payload, channel_layer, group_name):
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "agent.event",
            "payload": payload,
        },
    )


def is_cancelled(run_id, channel_layer, group_name):
    canceled = redis_client.get(f"agent:{run_id}:cancel") == "1"
    if canceled:
        emit(
            {
                "type": "cancelled",
                "run_id": run_id,
            },
            channel_layer,
            group_name,
        )
    return canceled


def wait_for_user(channel_layer, group_name, run_id, timeout_seconds=300):
    emit(
        {
            "type": "question",
            "message": "I need more input from you.",
        },
        channel_layer,
        group_name,
    )

    result = redis_client.blpop(
        f"agent:{run_id}:input",
        timeout=timeout_seconds,
    )

    if result is None:
        emit(
            {
                "type": "error",
                "message": "Timed out waiting for user input.",
            },
            channel_layer,
            group_name,
        )
        return None

    _, message = result
    return message
