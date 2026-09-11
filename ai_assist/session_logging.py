import logging

from django.db import transaction
from user.models import UserModel

from .models import AiAssistModelOutput, AiAssistSession, AiAssistUserInput


logger = logging.getLogger(__name__)


def create_session_for_user(run_id, username, workflow, initial_input):
    try:
        user = UserModel.get_by_username(username=username)
        if user:
            create_session(run_id, user, workflow, initial_input)
    except Exception:
        logger.exception("Unable to resolve user for AI assist session %s", run_id)


def create_session(run_id, user, workflow, initial_input):
    try:
        with transaction.atomic():
            session = AiAssistSession.objects.create(
                run_id=run_id, user=user, workflow=workflow
            )
            AiAssistUserInput.objects.create(
                session=session, sequence=1, content=initial_input
            )
    except Exception:
        logger.exception("Unable to create AI assist session log for %s", run_id)


def record_user_input(run_id, content):
    try:
        with transaction.atomic():
            session = AiAssistSession.objects.select_for_update().get(run_id=run_id)
            sequence = session.user_inputs.count() + 1
            AiAssistUserInput.objects.create(
                session=session, sequence=sequence, content=content
            )
    except Exception:
        logger.exception("Unable to record AI assist user input for %s", run_id)


def record_model_output(run_id, content, usage):
    try:
        with transaction.atomic():
            session = AiAssistSession.objects.select_for_update().get(run_id=run_id)
            sequence = session.model_outputs.count() + 1
            AiAssistModelOutput.objects.create(
                session=session, sequence=sequence, content=content
            )
            prompt_tokens = usage.get("prompt_tokens") or 0
            session.context_size += prompt_tokens
            session.prompt_tokens += prompt_tokens
            session.completion_tokens += usage.get("completion_tokens") or 0
            session.total_tokens += usage.get("total_tokens") or 0
            session.save(
                update_fields=(
                    "context_size",
                    "prompt_tokens",
                    "completion_tokens",
                    "total_tokens",
                )
            )
    except Exception:
        logger.exception("Unable to record AI assist model output for %s", run_id)
