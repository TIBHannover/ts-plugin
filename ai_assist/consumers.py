import json
import secrets
from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from celery import current_app
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

from .redis_client import redis_client


class AgentConsumer(AsyncWebsocketConsumer):
    """Bridge the browser socket and the Celery worker through Redis queues."""

    async def connect(self):
        self.run_id = str(self.scope["url_route"]["kwargs"]["run_id"])
        self.group_name = f"agent_run_{self.run_id}"
        token = parse_qs(self.scope["query_string"].decode()).get("token", [""])[0]
        expected_token = await sync_to_async(redis_client.get)(
            f"agent:{self.run_id}:socket_token"
        )
        if not expected_token or not secrets.compare_digest(token, expected_token):
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await sync_to_async(redis_client.rpush)(f"agent:{self.run_id}:ready", "1")
        await sync_to_async(redis_client.expire)(f"agent:{self.run_id}:ready", 60)

        await self.send_json(
            {
                "type": "connected",
                "run_id": self.run_id,
            }
        )

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # Feedback is queued for the next LLM turn. A clarification reply also
        # schedules a short resume task for the Redis-persisted conversation.
        if bytes_data is not None:
            await self.close(code=1003)
            return
        try:
            data = json.loads(text_data)
        except (TypeError, json.JSONDecodeError):
            await self.send_json({"type": "error", "message": "Invalid JSON."})
            return

        if data.get("type") == "cancel":
            await sync_to_async(redis_client.setex)(f"agent:{self.run_id}:cancel", 3600, "1")

        elif data.get("type") == "reject":
            waiting = await sync_to_async(redis_client.get)(
                f"agent:{self.run_id}:awaiting_rejection"
            )
            if not waiting:
                return
            resuming = await sync_to_async(redis_client.set)(
                f"agent:{self.run_id}:resuming", "1", nx=True, ex=60
            )
            if not resuming:
                return
            rejection_count = await sync_to_async(redis_client.incr)(
                f"agent:{self.run_id}:rejections"
            )
            await sync_to_async(redis_client.expire)(f"agent:{self.run_id}:rejections", 3600)
            if rejection_count <= settings.TERM_REQUEST_AI_ASSIST_MAX_REJECTIONS:
                await sync_to_async(redis_client.delete)(
                    f"agent:{self.run_id}:awaiting_rejection",
                    f"agent:{self.run_id}:resuming",
                )
                await sync_to_async(redis_client.setex)(
                    f"agent:{self.run_id}:awaiting_rejection_reason", 3600, "1"
                )
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "agent.event",
                        "payload": {
                            "type": "question",
                            "message": "Why do you reject this recommendation?",
                        },
                    },
                )
                return
            await self.resume_task("awaiting_rejection")

        elif data.get("type") == "user_message" and isinstance(data.get("message", ""), str):
            message = data.get("message", "")
            if len(message) > 4000:
                await self.send_json({"type": "error", "message": "Message is too long."})
                return
            awaiting_key = "awaiting_input"
            waiting = await sync_to_async(redis_client.get)(f"agent:{self.run_id}:{awaiting_key}")
            if not waiting:
                awaiting_key = "awaiting_rejection_reason"
                waiting = await sync_to_async(redis_client.get)(f"agent:{self.run_id}:{awaiting_key}")
            if not waiting:
                return
            resuming = await sync_to_async(redis_client.set)(
                f"agent:{self.run_id}:resuming", "1", nx=True, ex=60
            )
            if not resuming:
                return
            if awaiting_key == "awaiting_rejection_reason":
                message = f"The user rejected this recommendation because: {message}. Find a different suitable parent term."
            await sync_to_async(redis_client.rpush)(f"agent:{self.run_id}:input", message)
            await sync_to_async(redis_client.expire)(f"agent:{self.run_id}:input", 3600)
            await self.resume_task(awaiting_key)

    async def resume_task(self, awaiting_key):
        try:
            await sync_to_async(current_app.send_task)(
                "ai_assist.tasks.resume_agent_task", args=[self.run_id]
            )
        except Exception:
            await sync_to_async(redis_client.delete)(f"agent:{self.run_id}:resuming")
            await self.send_json({"type": "error", "message": "Unable to resume assistant."})
            return
        await sync_to_async(redis_client.delete)(
            f"agent:{self.run_id}:{awaiting_key}",
            f"agent:{self.run_id}:resuming",
        )

    async def agent_event(self, event):
        await self.send_json(event["payload"])

    async def send_json(self, payload):
        await self.send(text_data=json.dumps(payload))
