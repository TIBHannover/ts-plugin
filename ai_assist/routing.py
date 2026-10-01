from django.urls import path

from .workflow_consumer import WorkflowConsumer

websocket_urlpatterns = [
    path("ws/ai_assist/agent/<uuid:run_id>/", WorkflowConsumer.as_asgi()),
]
