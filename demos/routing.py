from django.urls import path

from .consumers import AgentConsumer


websocket_urlpatterns = [
    path("ws/demos/agent/<uuid:run_id>/", AgentConsumer.as_asgi()),
]
