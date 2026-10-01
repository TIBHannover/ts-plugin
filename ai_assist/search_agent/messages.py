from asgiref.sync import sync_to_async
from celery import current_app

from ai_assist.redis_client import redis_client
from ai_assist.transport import (
    REDIS_TRUE_VALUE,
    RESUME_TTL_SECONDS,
    RUN_REDIS_KEY_RESUMING,
    RUN_TTL_SECONDS,
    SERVER_MESSAGE_TYPE_ERROR,
    run_redis_key,
)

from .state import (
    CLIENT_MESSAGE_TYPE_REJECT,
    RUN_REDIS_KEY_AWAITING_REJECTION,
    RUN_REDIS_KEY_SEARCH_AGENT_REJECTIONS,
)

INVALID_MESSAGE_ERROR = (
    "Invalid message. Use 'cancel', 'reject', or "
    "'user_message' with a string 'message'."
)


async def handle_client_message(consumer, data):
    message_type = data.get("type") if isinstance(data, dict) else None
    if message_type != CLIENT_MESSAGE_TYPE_REJECT:
        await consumer.send_json(
            {"type": SERVER_MESSAGE_TYPE_ERROR, "message": INVALID_MESSAGE_ERROR}
        )
        return
    waiting = await sync_to_async(redis_client.get)(
        run_redis_key(consumer.run_id, RUN_REDIS_KEY_AWAITING_REJECTION)
    )
    if waiting != "search":
        return
    claimed = await sync_to_async(redis_client.set)(
        run_redis_key(consumer.run_id, RUN_REDIS_KEY_RESUMING),
        REDIS_TRUE_VALUE,
        nx=True,
        ex=RESUME_TTL_SECONDS,
    )
    if not claimed:
        return
    await sync_to_async(redis_client.incr)(
        run_redis_key(consumer.run_id, RUN_REDIS_KEY_SEARCH_AGENT_REJECTIONS)
    )
    await sync_to_async(redis_client.expire)(
        run_redis_key(consumer.run_id, RUN_REDIS_KEY_SEARCH_AGENT_REJECTIONS),
        RUN_TTL_SECONDS,
    )
    try:
        await sync_to_async(current_app.send_task)(
            "ai_assist.tasks.resume_agent_task", args=[consumer.run_id]
        )
    except Exception:
        await sync_to_async(redis_client.delete)(
            run_redis_key(consumer.run_id, RUN_REDIS_KEY_RESUMING)
        )
        await consumer.send_json(
            {"type": SERVER_MESSAGE_TYPE_ERROR, "message": "Unable to resume assistant."}
        )
        return
    await sync_to_async(redis_client.delete)(
        run_redis_key(consumer.run_id, RUN_REDIS_KEY_AWAITING_REJECTION),
        run_redis_key(consumer.run_id, RUN_REDIS_KEY_RESUMING),
    )
