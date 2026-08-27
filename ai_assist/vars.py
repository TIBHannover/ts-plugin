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

RUN_REDIS_KEY_PREFIX = "agent"
RUN_GROUP_PREFIX = "agent_run"
RUN_REDIS_KEY_CANCEL = "cancel"
RUN_REDIS_KEY_INPUT = "input"
RUN_REDIS_KEY_READY = "ready"
RUN_REDIS_KEY_STATE = "state"
RUN_REDIS_KEY_AWAITING_INPUT = "awaiting_input"
RUN_REDIS_KEY_AWAITING_REJECTION = "awaiting_rejection"
RUN_REDIS_KEY_AWAITING_REJECTION_REASON = "awaiting_rejection_reason"
RUN_REDIS_KEY_REJECTIONS = "rejections"
RUN_REDIS_KEY_RESUMING = "resuming"
RUN_REDIS_KEY_SOCKET_TOKEN = "socket_token"
RUN_REDIS_KEYS = (
    RUN_REDIS_KEY_CANCEL,
    RUN_REDIS_KEY_INPUT,
    RUN_REDIS_KEY_READY,
    RUN_REDIS_KEY_STATE,
    RUN_REDIS_KEY_AWAITING_INPUT,
    RUN_REDIS_KEY_AWAITING_REJECTION,
    RUN_REDIS_KEY_AWAITING_REJECTION_REASON,
    RUN_REDIS_KEY_REJECTIONS,
    RUN_REDIS_KEY_RESUMING,
    RUN_REDIS_KEY_SOCKET_TOKEN,
)
REDIS_TRUE_VALUE = "1"
RUN_TTL_SECONDS = 3600
READY_TTL_SECONDS = 60
RESUME_TTL_SECONDS = 60
READY_WAIT_TIMEOUT_SECONDS = 30
MAX_INITIAL_SEARCH_CALLS = 3

WEBSOCKET_TOKEN_QUERY_PARAMETER = "token"
WEBSOCKET_TOKEN_BYTES = 32
WEBSOCKET_CLOSE_CODE_UNAUTHORIZED = 4403
WEBSOCKET_CLOSE_CODE_BINARY_UNSUPPORTED = 1003
WEBSOCKET_PATH_TEMPLATE = "/ws/ai_assist/agent/{run_id}/"

CLIENT_MESSAGE_TYPE_CANCEL = "cancel"
CLIENT_MESSAGE_TYPE_REJECT = "reject"
CLIENT_MESSAGE_TYPE_USER_MESSAGE = "user_message"
SERVER_MESSAGE_TYPE_CONNECTED = "connected"
SERVER_MESSAGE_TYPE_AGENT_STARTED = "agent_started"
SERVER_MESSAGE_TYPE_QUESTION = "question"
SERVER_MESSAGE_TYPE_PROGRESS = "progress"
SERVER_MESSAGE_TYPE_DONE = "done"
SERVER_MESSAGE_TYPE_CANCELLED = "cancelled"
SERVER_MESSAGE_TYPE_ERROR = "error"
CHANNEL_EVENT_TYPE_AGENT_EVENT = "agent.event"
RESUME_AGENT_TASK_NAME = "ai_assist.tasks.resume_agent_task"


def run_redis_key(run_id, key):
    return f"{RUN_REDIS_KEY_PREFIX}:{run_id}:{key}"


def run_group_name(run_id):
    return f"{RUN_GROUP_PREFIX}_{run_id}"
