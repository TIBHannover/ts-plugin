import json
from channels.generic.websocket import AsyncWebsocketConsumer

from .redis_client import redis_client


class AgentConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.run_id = str(self.scope["url_route"]["kwargs"]["run_id"])
        self.group_name = f"agent_run_{self.run_id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        redis_client.rpush(f"agent:{self.run_id}:ready", "1")
        redis_client.expire(f"agent:{self.run_id}:ready", 60)

        await self.send_json(
            {
                "type": "connected",
                "run_id": self.run_id,
            }
        )

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        redis_client.setex(f"agent:{self.run_id}:cancel", 3600, "1")

    async def receive(self, payload):
        data = json.loads(payload)

        if data.get("type") == "cancel":
            redis_client.setex(f"agent:{self.run_id}:cancel", 3600, "1")

        elif data.get("type") == "user_message":
            redis_client.rpush(
                f"agent:{self.run_id}:input",
                data.get("message", ""),
            )

    async def agent_event(self, event):
        await self.send_json(event["payload"])

    async def send_json(self, payload):
        await self.send(text_data=json.dumps(payload))
