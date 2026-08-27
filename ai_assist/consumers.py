import json
import secrets
from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from celery import current_app
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

from .redis_client import redis_client
from .vars import (
    CHANNEL_EVENT_TYPE_AGENT_EVENT,
    CLIENT_MESSAGE_TYPE_CANCEL,
    CLIENT_MESSAGE_TYPE_REJECT,
    CLIENT_MESSAGE_TYPE_USER_MESSAGE,
    READY_TTL_SECONDS,
    REDIS_TRUE_VALUE,
    RESUME_AGENT_TASK_NAME,
    RESUME_TTL_SECONDS,
    RUN_REDIS_KEY_AWAITING_INPUT,
    RUN_REDIS_KEY_AWAITING_REJECTION,
    RUN_REDIS_KEY_AWAITING_REJECTION_REASON,
    RUN_REDIS_KEY_CANCEL,
    RUN_REDIS_KEY_INPUT,
    RUN_REDIS_KEY_READY,
    RUN_REDIS_KEY_REJECTIONS,
    RUN_REDIS_KEY_RESUMING,
    RUN_REDIS_KEY_SOCKET_TOKEN,
    RUN_TTL_SECONDS,
    SERVER_MESSAGE_TYPE_CONNECTED,
    SERVER_MESSAGE_TYPE_ERROR,
    SERVER_MESSAGE_TYPE_QUESTION,
    WEBSOCKET_CLOSE_CODE_BINARY_UNSUPPORTED,
    WEBSOCKET_CLOSE_CODE_UNAUTHORIZED,
    WEBSOCKET_TOKEN_QUERY_PARAMETER,
    run_group_name,
    run_redis_key,
)


class ClientMessage:
    CANCEL = CLIENT_MESSAGE_TYPE_CANCEL
    REJECT = CLIENT_MESSAGE_TYPE_REJECT
    USER_MESSAGE = CLIENT_MESSAGE_TYPE_USER_MESSAGE

    def __init__(self, message_type, message=None):
        self.message_type = message_type
        self._message = message

    @classmethod
    def from_data(cls, data):
        if not isinstance(data, dict):
            return None

        message_type = data.get("type")
        if message_type in (cls.CANCEL, cls.REJECT):
            return cls(message_type)
        if message_type == cls.USER_MESSAGE and isinstance(data.get("message"), str):
            return cls(message_type, data["message"])
        return None

    def is_cancel(self):
        return self.message_type == self.CANCEL

    def is_reject(self):
        return self.message_type == self.REJECT

    def is_user_message(self):
        return self.message_type == self.USER_MESSAGE

    def get_message(self):
        return self._message

    def set_message(self, message):
        self._message = message


class AgentConsumer(AsyncWebsocketConsumer):
    """Bridge the browser socket and the Celery worker through Redis queues."""

    async def connect(self):
        self.run_id = str(self.scope["url_route"]["kwargs"]["run_id"])
        self.group_name = run_group_name(self.run_id)
        token = parse_qs(self.scope["query_string"].decode()).get(
            WEBSOCKET_TOKEN_QUERY_PARAMETER, [""]
        )[0]
        expected_token = await sync_to_async(redis_client.get)(
            run_redis_key(self.run_id, RUN_REDIS_KEY_SOCKET_TOKEN)
        )
        if not expected_token or not secrets.compare_digest(token, expected_token):
            await self.close(code=WEBSOCKET_CLOSE_CODE_UNAUTHORIZED)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        ready_key = run_redis_key(self.run_id, RUN_REDIS_KEY_READY)
        await sync_to_async(redis_client.rpush)(ready_key, REDIS_TRUE_VALUE)
        await sync_to_async(redis_client.expire)(ready_key, READY_TTL_SECONDS)

        await self.send_json(
            {
                "type": SERVER_MESSAGE_TYPE_CONNECTED,
                "run_id": self.run_id,
            }
        )

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # Feedback is queued for the next LLM turn. A clarification reply also
        # schedules a short resume task for the Redis-persisted conversation.
        if bytes_data is not None:
            await self.close(code=WEBSOCKET_CLOSE_CODE_BINARY_UNSUPPORTED)
            return
        try:
            data = json.loads(text_data)
        except (TypeError, json.JSONDecodeError):
            await self.send_json(
                {"type": SERVER_MESSAGE_TYPE_ERROR, "message": "Invalid JSON."}
            )
            return

        message = ClientMessage.from_data(data)
        if message is None:
            await self.send_json(
                {
                    "type": SERVER_MESSAGE_TYPE_ERROR,
                    "message": (
                        "Invalid message. Use 'cancel', 'reject', or "
                        "'user_message' with a string 'message'."
                    ),
                }
            )
            return

        if message.is_cancel():
            await sync_to_async(redis_client.setex)(
                run_redis_key(self.run_id, RUN_REDIS_KEY_CANCEL),
                RUN_TTL_SECONDS,
                REDIS_TRUE_VALUE,
            )

        elif message.is_reject():
            # this is for handling the rejection request. we do not ask for the reason at this stage.
            # check whether there is a pending run waiting for a rejection. The task put it there after finishing the term request. user can reject a suggested term.
            waiting = await sync_to_async(redis_client.get)(
                run_redis_key(self.run_id, RUN_REDIS_KEY_AWAITING_REJECTION)
            )
            if not waiting:
                return
            # lock the rejection resuming with nx=True. lock is needed to make it idempotent. Multiple resuming for a run id is not possible.
            resuming = await sync_to_async(redis_client.set)(
                run_redis_key(self.run_id, RUN_REDIS_KEY_RESUMING),
                REDIS_TRUE_VALUE,
                nx=True,
                ex=RESUME_TTL_SECONDS,
            )
            if not resuming:
                return
            # increment the rejection count.
            rejection_count = await sync_to_async(redis_client.incr)(
                run_redis_key(self.run_id, RUN_REDIS_KEY_REJECTIONS)
            )
            # expire the counter after RUN_TTL_SECONDS.
            await sync_to_async(redis_client.expire)(
                run_redis_key(self.run_id, RUN_REDIS_KEY_REJECTIONS), RUN_TTL_SECONDS
            )
            # we allow a client to reject an agent answer for a certain amout of times.
            if rejection_count <= settings.TERM_REQUEST_AI_ASSIST_MAX_REJECTIONS:
                # remove awainting_rejection and resuming keys since we are about to run the agent again.
                await sync_to_async(redis_client.delete)(
                    run_redis_key(self.run_id, RUN_REDIS_KEY_AWAITING_REJECTION),
                    run_redis_key(self.run_id, RUN_REDIS_KEY_RESUMING),
                )
                # this tell the agent to treat the next user message as a reason for rejection.
                await sync_to_async(redis_client.setex)(
                    run_redis_key(self.run_id, RUN_REDIS_KEY_AWAITING_REJECTION_REASON),
                    RUN_TTL_SECONDS,
                    REDIS_TRUE_VALUE,
                )
                # tell the client to tell why she rejects the recommendation.
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": CHANNEL_EVENT_TYPE_AGENT_EVENT,
                        "payload": {
                            "type": SERVER_MESSAGE_TYPE_QUESTION,
                            "message": "Why do you reject this recommendation?",
                        },
                    },
                )
                return
            await self.resume_task(RUN_REDIS_KEY_AWAITING_REJECTION)

        elif message.is_user_message():
            # message is either user answer to agent question or the reason for rejection.
            user_message = message.get_message()
            if len(user_message) > settings.TERM_REQUEST_INPUT_MAX_LENGTH:
                await self.send_json(
                    {
                        "type": SERVER_MESSAGE_TYPE_ERROR,
                        "message": "Message is too long.",
                    }
                )
                return
            # first check whether an agent is waiting for a user input or not. This for when agent needs as question from the client.
            awaiting_key = RUN_REDIS_KEY_AWAITING_INPUT
            waiting = await sync_to_async(redis_client.get)(
                run_redis_key(self.run_id, awaiting_key)
            )
            # if not, check whether an agent is waiting for a reason for rejection or not.
            if not waiting:
                awaiting_key = RUN_REDIS_KEY_AWAITING_REJECTION_REASON
                waiting = await sync_to_async(redis_client.get)(
                    run_redis_key(self.run_id, awaiting_key)
                )
            if not waiting:
                return
            # tell the agent to resume. lock it to make it idempotent. it must resume only once.
            resuming = await sync_to_async(redis_client.set)(
                run_redis_key(self.run_id, RUN_REDIS_KEY_RESUMING),
                REDIS_TRUE_VALUE,
                nx=True,
                ex=RESUME_TTL_SECONDS,
            )
            if not resuming:
                return
            if awaiting_key == RUN_REDIS_KEY_AWAITING_REJECTION_REASON:
                message.set_message(
                    f"The user rejected this recommendation because: {user_message}. "
                    "Find a different suitable parent term."
                )
            # we rpush the message to redis list. rpush because the agent waits/blocks until a message is available.
            await sync_to_async(redis_client.rpush)(
                run_redis_key(self.run_id, RUN_REDIS_KEY_INPUT), message.get_message()
            )
            # we remove the message if no agent consumes it after RUN_TTL_SECONDS.
            await sync_to_async(redis_client.expire)(
                run_redis_key(self.run_id, RUN_REDIS_KEY_INPUT), RUN_TTL_SECONDS
            )
            await self.resume_task(awaiting_key)

    async def resume_task(self, awaiting_key):
        # this calls the celery task (agent) to resume the conversation.
        try:
            await sync_to_async(current_app.send_task)(
                RESUME_AGENT_TASK_NAME, args=[self.run_id]
            )
        except Exception:
            await sync_to_async(redis_client.delete)(
                run_redis_key(self.run_id, RUN_REDIS_KEY_RESUMING)
            )
            await self.send_json(
                {
                    "type": SERVER_MESSAGE_TYPE_ERROR,
                    "message": "Unable to resume assistant.",
                }
            )
            return
        # remove the awaiting key and resuming flag after the task is called successfully.
        await sync_to_async(redis_client.delete)(
            run_redis_key(self.run_id, awaiting_key),
            run_redis_key(self.run_id, RUN_REDIS_KEY_RESUMING),
        )

    async def agent_event(self, event):
        await self.send_json(event["payload"])

    async def send_json(self, payload):
        await self.send(text_data=json.dumps(payload))
