from ai_assist.transport import (
    RUN_REDIS_KEY_CANCEL,
    RUN_REDIS_KEY_INPUT,
    RUN_REDIS_KEY_READY,
    RUN_REDIS_KEY_RESUMING,
    RUN_REDIS_KEY_SOCKET_TOKEN,
    RUN_REDIS_KEY_STATE,
)

CATEGORIES = {
    "Material Object": ["physical object", "device", "artifact", "substance", "physical thing"],
    "Process": ["activity", "event", "action", "occurrence", "procedure"],
    "Agent": ["person", "organization", "software agent", "actor"],
    "Attribute": ["property", "characteristic", "quality", "feature", "parameter", "trait"],
    "Disposition": ["function", "capability", "tendency", "potential", "capacity", "role"],
    "Location": ["place", "site", "region", "position", "spatial area"],
    "Time Interval": ["period", "duration", "moment", "date", "schedule", "start", "end"],
    "Information Content": [
        "data",
        "data set",
        "document",
        "report",
        "message",
        "description",
        "specification",
    ],
}

RUN_REDIS_KEY_AWAITING_INPUT = "awaiting_input"
RUN_REDIS_KEY_AWAITING_REJECTION = "awaiting_rejection"
RUN_REDIS_KEY_AWAITING_REJECTION_REASON = "awaiting_rejection_reason"
RUN_REDIS_KEY_TERM_REQUEST_AGENT_REJECTIONS = "rejections"
RUN_REDIS_KEY_SEARCH_AGENT_REJECTIONS = "search_rejections"

TERM_REQUEST_AGENT_MAX_INITIAL_SEARCH_CALLS = 3
CLIENT_MESSAGE_TYPE_CANCEL = "cancel"
CLIENT_MESSAGE_TYPE_REJECT = "reject"
CLIENT_MESSAGE_TYPE_USER_MESSAGE = "user_message"
SERVER_MESSAGE_TYPE_QUESTION = "question"
SERVER_MESSAGE_TYPE_PROGRESS = "progress"
SERVER_MESSAGE_TYPE_DONE = "done"
SERVER_MESSAGE_TYPE_CANCELLED = "cancelled"
SERVER_MESSAGE_TYPE_AGENT_STARTED = "agent_started"
RESUME_TERM_REQUEST_SEARCH_AGENT_TASK_NAME = "ai_assist.tasks.resume_agent_task"

RUN_REDIS_KEYS = (
    RUN_REDIS_KEY_CANCEL,
    RUN_REDIS_KEY_INPUT,
    RUN_REDIS_KEY_READY,
    RUN_REDIS_KEY_STATE,
    RUN_REDIS_KEY_AWAITING_INPUT,
    RUN_REDIS_KEY_AWAITING_REJECTION,
    RUN_REDIS_KEY_AWAITING_REJECTION_REASON,
    RUN_REDIS_KEY_TERM_REQUEST_AGENT_REJECTIONS,
    RUN_REDIS_KEY_SEARCH_AGENT_REJECTIONS,
    RUN_REDIS_KEY_RESUMING,
    RUN_REDIS_KEY_SOCKET_TOKEN,
)


def new_response(phase="term_request"):
    return {
        "candidates": [],
        "error": None,
        "is_final": False,
        "usage_stats": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "search_call_count": 0,
        "successful_search_count": 0,
        "progress_feedback": "",
        "needs_user_input": False,
        "question": "",
        "phase": phase,
        "search_results": [],
        "excluded_search_candidates": [],
        "clarification_count": 0,
    }


def normalize_state(state):
    """Add fields missing from runs persisted before workflow support."""
    response = state.setdefault("response", {})
    if "phase" not in response:
        state.setdefault("workflow", "term_request")
        state.setdefault(
            "input_text",
            next(
                (
                    message.get("content", "")
                    for message in state.get("messages", [])
                    if message.get("role") == "user"
                ),
                "",
            ),
        )
    for key, value in new_response().items():
        response.setdefault(key, value)
    state.setdefault("steps", 0)
    return state
