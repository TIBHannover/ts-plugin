from ai_assist.consumers import AgentConsumer
from ai_assist.transport import SERVER_MESSAGE_TYPE_ERROR

from .messages import TermRequestSearchClientMessage, TermRequestSearchMessageHandler


class TermRequestSearchConsumer(AgentConsumer):
    invalid_message_error = (
        "Invalid message. Use 'cancel', 'reject', or "
        "'user_message' with a string 'message'."
    )

    async def handle_workflow_message(self, data):
        message = TermRequestSearchClientMessage.from_data(data)
        if message is None:
            await self.send_json(
                {"type": SERVER_MESSAGE_TYPE_ERROR, "message": self.invalid_message_error}
            )
            return
        await TermRequestSearchMessageHandler(self).handle(message)
