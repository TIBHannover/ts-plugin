from ai_assist.consumers import AgentConsumer
from asgiref.sync import sync_to_async

from ai_assist.redis_client import redis_client
from ai_assist.transport import (
    REDIS_TRUE_VALUE,
    RUN_REDIS_KEY_CANCEL,
    RUN_REDIS_KEY_STATE,
    RUN_TTL_SECONDS,
    SERVER_MESSAGE_TYPE_ERROR,
    run_redis_key,
)

class WorkflowConsumer(AgentConsumer):
    async def handle_workflow_message(self, data):
        if isinstance(data, dict) and data.get("type") == "cancel":
            await sync_to_async(redis_client.setex)(
                run_redis_key(self.run_id, RUN_REDIS_KEY_CANCEL),
                RUN_TTL_SECONDS,
                REDIS_TRUE_VALUE,
            )
            return
        state_json = await sync_to_async(redis_client.get)(
            run_redis_key(self.run_id, RUN_REDIS_KEY_STATE)
        )
        if not state_json:
            await self.send_json(
                {"type": SERVER_MESSAGE_TYPE_ERROR, "message": "Assistant is not ready."}
            )
            return
        import json

        try:
            state = json.loads(state_json)
        except (TypeError, json.JSONDecodeError):
            await self.send_json(
                {"type": SERVER_MESSAGE_TYPE_ERROR, "message": "Assistant is not ready."}
            )
            return
        if state.get("workflow") == "search":
            from ai_assist.search_agent.messages import handle_client_message

            await handle_client_message(self, data)
            return
        from ai_assist.term_request_assist.consumer import handle_client_message

        await handle_client_message(self, data)
