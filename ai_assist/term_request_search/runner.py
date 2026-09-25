import json
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings

from .agent import run_term_request_or_search_agent_turn
from .prompts import SEARCH_AGENT_PROMPT, TERM_REQUEST_AGENT_PROMPT
from ai_assist.transport import (
    CHANNEL_EVENT_TYPE_AGENT_EVENT,
    READY_WAIT_TIMEOUT_SECONDS,
    REDIS_TRUE_VALUE,
    RUN_REDIS_KEY_CANCEL,
    RUN_REDIS_KEY_INPUT,
    RUN_REDIS_KEY_READY,
    RUN_REDIS_KEY_STATE,
    RUN_TTL_SECONDS,
    SERVER_MESSAGE_TYPE_ERROR,
    run_group_name,
    run_redis_key,
)
from ai_assist.redis_client import redis_client
from .state import (
    AWAITING_REJECTION_TERM_REQUEST_SEARCH,
    RUN_REDIS_KEYS,
    RUN_REDIS_KEY_AWAITING_INPUT,
    RUN_REDIS_KEY_AWAITING_REJECTION,
    RUN_REDIS_KEY_SEARCH_AGENT_REJECTIONS,
    RUN_REDIS_KEY_TERM_REQUEST_AGENT_REJECTIONS,
    SERVER_MESSAGE_TYPE_AGENT_STARTED,
    SERVER_MESSAGE_TYPE_CANCELLED,
    SERVER_MESSAGE_TYPE_DONE,
    SERVER_MESSAGE_TYPE_PROGRESS,
    SERVER_MESSAGE_TYPE_QUESTION,
    SERVER_MESSAGE_TYPE_ONTOLOGY_SELECTION,
    get_term_category,
    new_response,
    normalize_state,
)

logger = logging.getLogger(__name__)

TERM_REQUEST_AGENT_MAX_LOOPS = settings.TERM_REQUEST_AI_ASSIST_MAX_LOOPS
SEARCH_AGENT_MAX_LOOPS = settings.SEARCH_AI_ASSIST_MAX_LOOPS
TERM_REQUEST_AGENT_MAX_REJECTIONS = settings.TERM_REQUEST_AI_ASSIST_MAX_REJECTIONS


def run_term_request_search_agent(
    run_id, input_text, workflow="term_request", search_inputs=None
):
    # the task gets triggered by the client when calling the start_agent view.
    try:
        if not redis_client.blpop(
            run_redis_key(run_id, RUN_REDIS_KEY_READY),
            timeout=READY_WAIT_TIMEOUT_SECONDS,
        ):
            cleanup_run(run_id)
            return
        phase = "search"
        search_inputs = search_inputs if workflow == "term_request" else None
        search_inputs = search_inputs or [input_text]
        state = {
            "messages": [
                {
                    "role": "system",
                    "content": (
                        SEARCH_AGENT_PROMPT
                        if phase == "search"
                        else TERM_REQUEST_AGENT_PROMPT
                    ),
                },
                {"role": "user", "content": search_inputs[0]},
            ],
            "response": new_response(phase),
            "steps": 0,
            "workflow": workflow,
            "input_text": input_text,
            "search_inputs": search_inputs,
            "search_input_index": 0,
            "search_candidates": [],
        }
        state["response"]["project_domain_provided"] = has_project_domain(input_text)
        emit(
            {
                "type": SERVER_MESSAGE_TYPE_AGENT_STARTED,
                "run_id": run_id,
                "input": input_text,
            },
            run_id,
        )
        run_conversation(run_id, state)
    except Exception:
        logger.exception("Unable to start AI assist run %s", run_id)
        fail_run(run_id)


def resume_term_request_search_agent(run_id):
    # this runs when there is an event in the redis queue that indicates the agent should resume.
    try:
        state_json = redis_client.get(run_redis_key(run_id, RUN_REDIS_KEY_STATE))
        if not state_json:
            return
        state = normalize_state(json.loads(state_json))
        rejection_key = (
            RUN_REDIS_KEY_SEARCH_AGENT_REJECTIONS
            if state["response"].get("phase") == "search"
            else RUN_REDIS_KEY_TERM_REQUEST_AGENT_REJECTIONS
        )
        rejection_count = int(
            redis_client.get(run_redis_key(run_id, rejection_key)) or 0
        )
        if (
            state.get("workflow") == "term_request"
            and state["response"].get("phase") == "search"
            and rejection_count
        ):
            start_term_request_phase(state)
            redis_client.delete(
                run_redis_key(run_id, RUN_REDIS_KEY_SEARCH_AGENT_REJECTIONS)
            )
            rejection_count = 0
        elif rejection_count > TERM_REQUEST_AGENT_MAX_REJECTIONS:
            if state["response"].get("phase") == "search":
                emit_no_candidates_found(run_id, "search")
            else:
                emit_no_parent_found(run_id)
            cleanup_run(run_id)
            return
        if rejection_count > state.get("retry_started", 0):
            state["steps"] = 0
            state["retry_started"] = rejection_count
            state["response"]["search_call_count"] = 0
            if state["response"]["phase"] == "search":
                state["response"]["successful_search_count"] = 0
                state["response"]["excluded_search_candidates"].extend(
                    {"ontologyId": candidate["ontologyId"], "iri": candidate["iri"]}
                    for candidate in state["response"]["candidates"]
                )
                state["response"]["search_results"] = []
                state["response"]["candidates"] = []
            else:
                state["response"]["allow_ontology_reselection"] = False
                state["response"]["pending_ontology_rejection_decision"] = True
        elif (
            state["response"].get("phase") == "term_request"
            and state["response"].get("needs_user_input")
        ):
            state["steps"] = 0
        state["response"]["needs_user_input"] = False
        state["response"]["question"] = ""
        state["response"]["is_final"] = False
        run_conversation(run_id, state)
    except Exception:
        logger.exception("Unable to resume AI assist run %s", run_id)
        fail_run(run_id)


def run_conversation(run_id, state):
    try:
        response = state["response"]
        messages = state["messages"]
        max_loops = (
            SEARCH_AGENT_MAX_LOOPS
            if response["phase"] == "search"
            else TERM_REQUEST_AGENT_MAX_LOOPS
        )
        for step in range(state["steps"], max_loops):
            if is_cancelled(run_id):
                cleanup_run(run_id)
                return

            add_pending_user_input(messages, run_id)
            run_term_request_or_search_agent_turn(
                messages,
                response,
                run_id,
                lambda message: emit(
                    {"type": SERVER_MESSAGE_TYPE_PROGRESS, "message": message}, run_id
                ),
            )
            state["steps"] = step + 1

            if response["needs_ontology_selection"]:
                save_state(run_id, state)
                emit(
                    {
                        "type": SERVER_MESSAGE_TYPE_ONTOLOGY_SELECTION,
                        "message": "Choose the ontology to use for the term request.",
                        "ontologies": response["ontology_options"],
                    },
                    run_id,
                )
                return

            if response["needs_user_input"]:
                save_state(run_id, state)
                emit(
                    {
                        "type": SERVER_MESSAGE_TYPE_QUESTION,
                        "message": response["question"],
                    },
                    run_id,
                )
                return

            if response["is_final"]:
                if (
                    state.get("workflow") == "term_request"
                    and response["phase"] == "search"
                ):
                    if finish_term_request_search_pass(state):
                        run_conversation(run_id, state)
                        return
                    if not response["candidates"]:
                        start_term_request_phase(state)
                        run_conversation(run_id, state)
                        return
                preliminary_search = (
                    state.get("workflow") == "term_request"
                    and response["phase"] == "search"
                )
                save_state(
                    run_id,
                    state,
                    RUN_REDIS_KEY_AWAITING_REJECTION,
                    (
                        AWAITING_REJECTION_TERM_REQUEST_SEARCH
                        if preliminary_search
                        else None
                    ),
                )
                emit_done(
                    response,
                    run_id,
                    "The target term might already exist."
                    if preliminary_search
                    else None,
                )
                return

            progress_feedbacks = [] if response.get("progress_emitted_live") else (
                response.get("progress_feedbacks")
                or (
                    [response["progress_feedback"]]
                    if response.get("progress_feedback")
                    else []
                )
            )
            for progress_feedback in progress_feedbacks:
                emit(
                    {
                        "type": SERVER_MESSAGE_TYPE_PROGRESS,
                        "message": progress_feedback,
                    },
                    run_id,
                )

        emit(
            {
                "type": SERVER_MESSAGE_TYPE_ERROR,
                "message": f"Agent reached the {max_loops}-step limit without a final response.",
            },
            run_id,
        )
        cleanup_run(run_id)
    except Exception:
        logger.exception("AI assist conversation failed for run %s", run_id)
        fail_run(run_id)


def save_state(
    run_id, state, awaiting_key=RUN_REDIS_KEY_AWAITING_INPUT, awaiting_value=None
):
    # this saves two things in redis: the last state for the agnet and also the action key for the next step for the consumer
    redis_client.setex(
        run_redis_key(run_id, RUN_REDIS_KEY_STATE), RUN_TTL_SECONDS, json.dumps(state)
    )
    redis_client.setex(
        run_redis_key(run_id, awaiting_key),
        RUN_TTL_SECONDS,
        (
            awaiting_value
            or state["response"]["phase"]
            if awaiting_key == RUN_REDIS_KEY_AWAITING_REJECTION
            else REDIS_TRUE_VALUE
        ),
    )


def emit_done(response, run_id, message=None):
    payload = {
        "type": SERVER_MESSAGE_TYPE_DONE,
        "candidates": response.get("candidates", []),
        "error": response.get("error", ""),
    }
    if message:
        payload["message"] = message
    emit(payload, run_id)


def emit_no_candidates_found(run_id, phase):
    subject = "matching term" if phase == "search" else "suitable parent term"
    emit(
        {
            "type": SERVER_MESSAGE_TYPE_DONE,
            "candidates": [],
            "error": f"Unable to find a {subject} after {TERM_REQUEST_AGENT_MAX_REJECTIONS + 1} rejected recommendations.",
        },
        run_id,
    )


def emit_no_parent_found(run_id):
    """Backward-compatible alias for the original task helper."""
    emit_no_candidates_found(run_id, "term_request")


def start_term_request_phase(state):
    state["messages"] = [
        {"role": "system", "content": TERM_REQUEST_AGENT_PROMPT},
        {"role": "user", "content": state["input_text"]},
    ]
    state["response"] = new_response("term_request")
    state["response"]["term_category"] = get_term_category(state["input_text"])
    state["response"]["project_domain_provided"] = has_project_domain(
        state["input_text"]
    )
    state["steps"] = 0


def finish_term_request_search_pass(state):
    response = state["response"]
    candidates = state.setdefault("search_candidates", [])
    candidate_ids = {
        (candidate["ontologyId"].casefold(), candidate["iri"])
        for candidate in candidates
    }
    for candidate in response["candidates"][:5]:
        candidate_id = (candidate["ontologyId"].casefold(), candidate["iri"])
        if candidate_id not in candidate_ids:
            candidates.append(candidate)
            candidate_ids.add(candidate_id)

    search_inputs = state.get("search_inputs") or [state["input_text"]]
    next_index = state.get("search_input_index", 0) + 1
    if next_index >= len(search_inputs):
        response["candidates"] = candidates[:10]
        if response["candidates"]:
            response["error"] = None
        return False

    state["search_input_index"] = next_index
    state["messages"] = [
        {"role": "system", "content": SEARCH_AGENT_PROMPT},
        {"role": "user", "content": search_inputs[next_index]},
    ]
    state["response"] = new_response("search")
    state["response"]["excluded_search_candidates"] = [
        {"ontologyId": candidate["ontologyId"], "iri": candidate["iri"]}
        for candidate in candidates
    ]
    state["steps"] = 0
    return True


def has_project_domain(input_text):
    return any(
        line.partition(":")[2].strip()
        for line in input_text.splitlines()
        if line.startswith("Project domain:")
    )


def emit(payload, run_id):
    # send a message to the client holding the websocket connection. consumers.py handles this message in agent_event.
    async_to_sync(get_channel_layer().group_send)(
        run_group_name(run_id),
        {"type": CHANNEL_EVENT_TYPE_AGENT_EVENT, "payload": payload},
    )


def is_cancelled(run_id):
    if (
        redis_client.get(run_redis_key(run_id, RUN_REDIS_KEY_CANCEL))
        != REDIS_TRUE_VALUE
    ):
        return False
    emit({"type": SERVER_MESSAGE_TYPE_CANCELLED, "run_id": run_id}, run_id)
    return True


def add_pending_user_input(messages, run_id):
    """Drain queued feedback in FIFO order before the assistant's next LLM turn."""
    while message := redis_client.lpop(run_redis_key(run_id, RUN_REDIS_KEY_INPUT)):
        messages.append({"role": "user", "content": message})


def cleanup_run(run_id):
    """Remove the Redis data associated with a completed or failed run."""
    redis_client.delete(*(run_redis_key(run_id, key) for key in RUN_REDIS_KEYS))


def fail_run(run_id):
    """Notify the client about an unexpected failure and release all run state."""
    try:
        emit(
            {"type": SERVER_MESSAGE_TYPE_ERROR, "message": "Assistant run failed."},
            run_id,
        )
    finally:
        cleanup_run(run_id)
