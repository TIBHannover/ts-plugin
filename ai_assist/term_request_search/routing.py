from django.urls import path

from .consumer import TermRequestSearchConsumer

websocket_urlpatterns = [
    path(
        "ws/ai_assist/agent/<uuid:run_id>/",
        TermRequestSearchConsumer.as_asgi(),
    ),
]
