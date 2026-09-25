import json

from asgiref.sync import sync_to_async
from celery import current_app
from django.conf import settings

from ai_assist.redis_client import redis_client
from ai_assist.session_logging import record_user_input
from ai_assist.transport import (
    CHANNEL_EVENT_TYPE_AGENT_EVENT,
    REDIS_TRUE_VALUE,
    RESUME_TTL_SECONDS,
    RUN_REDIS_KEY_CANCEL,
    RUN_REDIS_KEY_INPUT,
    RUN_REDIS_KEY_RESUMING,
    RUN_REDIS_KEY_STATE,
    RUN_TTL_SECONDS,
    SERVER_MESSAGE_TYPE_ERROR,
    run_redis_key,
)
from .state import (
    AWAITING_REJECTION_TERM_REQUEST_SEARCH,
    CLIENT_MESSAGE_TYPE_CANCEL,
    CLIENT_MESSAGE_TYPE_REJECT,
    CLIENT_MESSAGE_TYPE_USER_MESSAGE,
    CLIENT_MESSAGE_TYPE_SELECT_ONTOLOGY,
    RESUME_TERM_REQUEST_SEARCH_AGENT_TASK_NAME,
    RUN_REDIS_KEY_AWAITING_INPUT,
    RUN_REDIS_KEY_AWAITING_REJECTION,
    RUN_REDIS_KEY_AWAITING_REJECTION_REASON,
    RUN_REDIS_KEY_SEARCH_AGENT_REJECTIONS,
    RUN_REDIS_KEY_TERM_REQUEST_AGENT_REJECTIONS,
    SERVER_MESSAGE_TYPE_PROGRESS,
    SERVER_MESSAGE_TYPE_QUESTION,
)


class TermRequestSearchClientMessage:
    CANCEL = CLIENT_MESSAGE_TYPE_CANCEL
    REJECT = CLIENT_MESSAGE_TYPE_REJECT
    USER_MESSAGE = CLIENT_MESSAGE_TYPE_USER_MESSAGE
    SELECT_ONTOLOGY = CLIENT_MESSAGE_TYPE_SELECT_ONTOLOGY

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
        if message_type == cls.SELECT_ONTOLOGY and isinstance(data.get("ontologyId"), str):
            return cls(message_type, data["ontologyId"])
        return None

    def is_cancel(self):
        return self.message_type == self.CANCEL

    def is_reject(self):
        return self.message_type == self.REJECT

    def is_user_message(self):
        return self.message_type == self.USER_MESSAGE

    def is_ontology_selection(self):
        return self.message_type == self.SELECT_ONTOLOGY

    def get_message(self):
        return self._message

    def set_message(self, message):
        self._message = message


class TermRequestSearchMessageHandler:
    """Coordinate term-request and search feedback for an assistant socket."""

    def __init__(self, consumer):
        self.consumer = consumer

    async def handle(self, message):
        if message.is_cancel():
            await sync_to_async(redis_client.setex)(
                run_redis_key(self.consumer.run_id, RUN_REDIS_KEY_CANCEL),
                RUN_TTL_SECONDS,
                REDIS_TRUE_VALUE,
            )
        elif message.is_reject():
            await self.handle_rejection()
        elif message.is_user_message():
            await self.handle_user_message(message)
        elif message.is_ontology_selection():
            await self.handle_ontology_selection(message.get_message())

    async def handle_ontology_selection(self, ontology_id):
        awaiting_key = RUN_REDIS_KEY_AWAITING_INPUT
        waiting = await sync_to_async(redis_client.get)(
            run_redis_key(self.consumer.run_id, awaiting_key)
        )
        if not waiting:
            return
        resuming = await sync_to_async(redis_client.set)(
            run_redis_key(self.consumer.run_id, RUN_REDIS_KEY_RESUMING),
            REDIS_TRUE_VALUE,
            nx=True,
            ex=RESUME_TTL_SECONDS,
        )
        if not resuming:
            return

        state_key = run_redis_key(self.consumer.run_id, RUN_REDIS_KEY_STATE)
        state_json = await sync_to_async(redis_client.get)(state_key)
        state = json.loads(state_json) if state_json else {}
        response = state.get("response", {})
        valid_ids = {
            option.get("ontologyId")
            for option in response.get("ontology_options", [])
            if isinstance(option, dict)
        }
        if not response.get("needs_ontology_selection") or ontology_id not in valid_ids:
            await sync_to_async(redis_client.delete)(
                run_redis_key(self.consumer.run_id, RUN_REDIS_KEY_RESUMING)
            )
            await self.consumer.send_json(
                {
                    "type": SERVER_MESSAGE_TYPE_ERROR,
                    "message": "Select one of the suggested ontologies.",
                }
            )
            return

        response["selected_ontology_ids"] = [ontology_id]
        response["needs_ontology_selection"] = False
        state.setdefault("messages", []).append(
            {
                "role": "user",
                "content": f'The user selected ontology "{ontology_id}". Continue with this ontology.',
            }
        )
        await sync_to_async(redis_client.setex)(
            state_key, RUN_TTL_SECONDS, json.dumps(state)
        )
        await sync_to_async(record_user_input)(self.consumer.run_id, ontology_id)
        await self.resume_task(awaiting_key)

    async def handle_rejection(self):
        waiting = await sync_to_async(redis_client.get)(
            run_redis_key(self.consumer.run_id, RUN_REDIS_KEY_AWAITING_REJECTION)
        )
        if not waiting:
            return
        resuming = await sync_to_async(redis_client.set)(
            run_redis_key(self.consumer.run_id, RUN_REDIS_KEY_RESUMING),
            REDIS_TRUE_VALUE,
            nx=True,
            ex=RESUME_TTL_SECONDS,
        )
        if not resuming:
            return
        rejection_key = (
            RUN_REDIS_KEY_SEARCH_AGENT_REJECTIONS
            if waiting in ("search", AWAITING_REJECTION_TERM_REQUEST_SEARCH)
            else RUN_REDIS_KEY_TERM_REQUEST_AGENT_REJECTIONS
        )
        try:
            rejection_count = await sync_to_async(redis_client.incr)(
                run_redis_key(self.consumer.run_id, rejection_key)
            )
            await sync_to_async(redis_client.expire)(
                run_redis_key(self.consumer.run_id, rejection_key), RUN_TTL_SECONDS
            )
        except Exception:
            await self.fail_resume()
            return
        if waiting == AWAITING_REJECTION_TERM_REQUEST_SEARCH:
            try:
                claimed = await sync_to_async(redis_client.getdel)(
                    run_redis_key(
                        self.consumer.run_id, RUN_REDIS_KEY_AWAITING_REJECTION
                    )
                )
            except Exception:
                await sync_to_async(redis_client.set)(
                    run_redis_key(
                        self.consumer.run_id, RUN_REDIS_KEY_AWAITING_REJECTION
                    ),
                    AWAITING_REJECTION_TERM_REQUEST_SEARCH,
                    nx=True,
                    ex=RUN_TTL_SECONDS,
                )
                await self.fail_resume()
                return
            if claimed != waiting:
                await sync_to_async(redis_client.delete)(
                    run_redis_key(self.consumer.run_id, RUN_REDIS_KEY_RESUMING)
                )
                return
            await self.resume_task(
                RUN_REDIS_KEY_AWAITING_REJECTION,
                restore_value=AWAITING_REJECTION_TERM_REQUEST_SEARCH,
            )
            return
        if rejection_count <= settings.TERM_REQUEST_AI_ASSIST_MAX_REJECTIONS:
            await sync_to_async(redis_client.delete)(
                run_redis_key(self.consumer.run_id, RUN_REDIS_KEY_AWAITING_REJECTION),
                run_redis_key(self.consumer.run_id, RUN_REDIS_KEY_RESUMING),
            )
            await sync_to_async(redis_client.setex)(
                run_redis_key(
                    self.consumer.run_id, RUN_REDIS_KEY_AWAITING_REJECTION_REASON
                ),
                RUN_TTL_SECONDS,
                REDIS_TRUE_VALUE,
            )
            await self.consumer.channel_layer.group_send(
                self.consumer.group_name,
                {
                    "type": CHANNEL_EVENT_TYPE_AGENT_EVENT,
                    "payload": {
                        "type": SERVER_MESSAGE_TYPE_QUESTION,
                        "message": "Why do you reject these recommendations?",
                    },
                },
            )
            return
        await self.resume_task(RUN_REDIS_KEY_AWAITING_REJECTION)

    async def handle_user_message(self, message):
        user_message = message.get_message()
        if len(user_message) > settings.TERM_REQUEST_INPUT_MAX_LENGTH:
            await self.consumer.send_json(
                {"type": SERVER_MESSAGE_TYPE_ERROR, "message": "Message is too long."}
            )
            return
        awaiting_key = RUN_REDIS_KEY_AWAITING_INPUT
        waiting = await sync_to_async(redis_client.get)(
            run_redis_key(self.consumer.run_id, awaiting_key)
        )
        if not waiting:
            awaiting_key = RUN_REDIS_KEY_AWAITING_REJECTION_REASON
            waiting = await sync_to_async(redis_client.get)(
                run_redis_key(self.consumer.run_id, awaiting_key)
            )
        if not waiting:
            return
        resuming = await sync_to_async(redis_client.set)(
            run_redis_key(self.consumer.run_id, RUN_REDIS_KEY_RESUMING),
            REDIS_TRUE_VALUE,
            nx=True,
            ex=RESUME_TTL_SECONDS,
        )
        if not resuming:
            return
        await sync_to_async(record_user_input)(self.consumer.run_id, user_message)
        if awaiting_key == RUN_REDIS_KEY_AWAITING_REJECTION_REASON:
            message.set_message(
                f"The user rejected these recommendations because: {user_message}. "
                "Interpret the full feedback semantically, without fuzzy or keyword "
                "matching. First return only JSON as {\"ontology_rejected\": true} if "
                "the user explicitly says the selected ontology itself is not a fit, or "
                "{\"ontology_rejected\": false} for feedback about the candidates, "
                "branch, specificity, or broadness. Do not call a tool for this decision."
            )
        await sync_to_async(redis_client.rpush)(
            run_redis_key(self.consumer.run_id, RUN_REDIS_KEY_INPUT),
            message.get_message(),
        )
        await sync_to_async(redis_client.expire)(
            run_redis_key(self.consumer.run_id, RUN_REDIS_KEY_INPUT), RUN_TTL_SECONDS
        )
        if awaiting_key == RUN_REDIS_KEY_AWAITING_REJECTION_REASON:
            await self.consumer.channel_layer.group_send(
                self.consumer.group_name,
                {
                    "type": CHANNEL_EVENT_TYPE_AGENT_EVENT,
                    "payload": {
                        "type": SERVER_MESSAGE_TYPE_PROGRESS,
                        "message": "Reviewing your feedback and deciding whether to select a different ontology.",
                    },
                },
            )
        await self.resume_task(awaiting_key)

    async def resume_task(self, awaiting_key, restore_value=None):
        try:
            await sync_to_async(current_app.send_task)(
                RESUME_TERM_REQUEST_SEARCH_AGENT_TASK_NAME,
                args=[self.consumer.run_id],
            )
        except Exception:
            if restore_value:
                await sync_to_async(redis_client.set)(
                    run_redis_key(self.consumer.run_id, awaiting_key),
                    restore_value,
                    nx=True,
                    ex=RUN_TTL_SECONDS,
                )
            await self.fail_resume()
            return
        keys = [run_redis_key(self.consumer.run_id, RUN_REDIS_KEY_RESUMING)]
        if not restore_value:
            keys.insert(0, run_redis_key(self.consumer.run_id, awaiting_key))
        await sync_to_async(redis_client.delete)(*keys)

    async def fail_resume(self):
        await sync_to_async(redis_client.delete)(
            run_redis_key(self.consumer.run_id, RUN_REDIS_KEY_RESUMING)
        )
        await self.consumer.send_json(
            {
                "type": SERVER_MESSAGE_TYPE_ERROR,
                "message": "Unable to resume assistant.",
            }
        )
