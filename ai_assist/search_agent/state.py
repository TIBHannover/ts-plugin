from ai_assist.transport import (
    RUN_REDIS_KEY_CANCEL,
    RUN_REDIS_KEY_INPUT,
    RUN_REDIS_KEY_READY,
    RUN_REDIS_KEY_RESUMING,
    RUN_REDIS_KEY_SOCKET_TOKEN,
    RUN_REDIS_KEY_STATE,
)

RUN_REDIS_KEY_AWAITING_REJECTION = "awaiting_rejection"
RUN_REDIS_KEY_SEARCH_AGENT_REJECTIONS = "search_rejections"
CLIENT_MESSAGE_TYPE_REJECT = "reject"
CLIENT_MESSAGE_TYPE_USER_MESSAGE = "user_message"
SERVER_MESSAGE_TYPE_AGENT_STARTED = "agent_started"
SERVER_MESSAGE_TYPE_CANCELLED = "cancelled"
SERVER_MESSAGE_TYPE_DONE = "done"
SERVER_MESSAGE_TYPE_PROGRESS = "progress"

RUN_REDIS_KEYS = (
    RUN_REDIS_KEY_CANCEL,
    RUN_REDIS_KEY_INPUT,
    RUN_REDIS_KEY_READY,
    RUN_REDIS_KEY_STATE,
    RUN_REDIS_KEY_AWAITING_REJECTION,
    RUN_REDIS_KEY_SEARCH_AGENT_REJECTIONS,
    RUN_REDIS_KEY_RESUMING,
    RUN_REDIS_KEY_SOCKET_TOKEN,
)


def new_response():
    return {
        "candidates": [],
        "error": None,
        "is_final": False,
        "usage_stats": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "search_call_count": 0,
        "successful_search_count": 0,
        "progress_feedback": "",
        "progress_feedbacks": [],
        "progress_emitted_live": False,
        "phase": "search",
        "search_results": [],
        "excluded_search_candidates": [],
        "invalid_final_response_count": 0,
    }


def normalize_state(state):
    response = state.setdefault("response", {})
    for key, value in new_response().items():
        response.setdefault(key, value)
    state.setdefault("workflow", "search")
    state.setdefault("steps", 0)
    return state
