import json
import secrets
from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

from .redis_client import redis_client
from .transport import (
    READY_TTL_SECONDS,
    REDIS_TRUE_VALUE,
    RUN_REDIS_KEY_READY,
    RUN_REDIS_KEY_SOCKET_TOKEN,
    SERVER_MESSAGE_TYPE_CONNECTED,
    SERVER_MESSAGE_TYPE_ERROR,
    WEBSOCKET_CLOSE_CODE_BINARY_UNSUPPORTED,
    WEBSOCKET_CLOSE_CODE_UNAUTHORIZED,
    WEBSOCKET_TOKEN_QUERY_PARAMETER,
    run_group_name,
    run_redis_key,
)


class AgentConsumer(AsyncWebsocketConsumer):
    """Provide generic WebSocket transport for an assistant workflow."""

    async def connect(self):
        self.group_name = None
        if not settings.AI_ASSIST_ENABLED:
            await self.close(code=WEBSOCKET_CLOSE_CODE_UNAUTHORIZED)
            return

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
            {"type": SERVER_MESSAGE_TYPE_CONNECTED, "run_id": self.run_id}
        )

    async def disconnect(self, close_code):
        if self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
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
        await self.handle_workflow_message(data)

    async def handle_workflow_message(self, data):
        raise NotImplementedError

    async def agent_event(self, event):
        await self.send_json(event["payload"])

    async def send_json(self, payload):
        await self.send(text_data=json.dumps(payload))
