import json
import uuid
from channels.generic.websocket import AsyncWebsocketConsumer

from .tasks import run_agent_task
from .redis_client import redis_client


class AgentConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.run_id = str(uuid.uuid4())
        self.group_name = f"agent_run_{self.run_id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

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

        if data["type"] == "start":
            task = run_agent_task.delay(
                run_id=self.run_id,
                input_text=data.get("input", ""),
            )

            await self.send_json(
                {
                    "type": "started",
                    "run_id": self.run_id,
                    "task_id": task.id,
                }
            )

        elif data["type"] == "cancel":
            redis_client.setex(f"agent:{self.run_id}:cancel", 3600, "1")

        elif data["type"] == "user_message":
            redis_client.rpush(
                f"agent:{self.run_id}:input",
                data.get("message", ""),
            )

    async def agent_event(self, event):
        await self.send_json(event["payload"])

    async def send_json(self, payload):
        await self.send(text_data=json.dumps(payload))
