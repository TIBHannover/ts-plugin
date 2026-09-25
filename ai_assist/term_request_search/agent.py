from concurrent.futures import ThreadPoolExecutor
import json
import logging
import os
from typing import Any

from openai import OpenAI

from ai_assist.session_logging import record_model_output
from . import search_agent, structural_agent
from .functions import (
    TERM_REQUEST_SEARCH_FUNCTIONS,
    TERM_REQUEST_SEARCH_TOOLS,
    get_term_detail,
)
from .state import TERM_REQUEST_AGENT_MAX_INITIAL_SEARCH_CALLS

logger = logging.getLogger(__name__)

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["LLM_API_KEY"],
)
MODEL = os.environ["LLM_MODEL"]
MAX_TERM_REQUEST_CLARIFICATIONS = 2
MAX_ONTOLOGY_SELECTION_FAILURES = 2


FUNCTION_LABELS = {
    "batch_search": "Searching terminology",
    "search_under_term": "Searching related terms",
    "get_term_detail": "Checking term details",
    "search_in_children": "Searching child terms",
    "get_roots": "Checking root terms",
    "get_individuals": "Checking individuals",
    "get_ontology_detail": "Checking ontology details",
    "ontologies_list": "Listing ontologies",
    "find_category_terms": "Locating the category subtree",
}
TERM_REQUEST_TOOL_NAMES = structural_agent.STRUCTURAL_TOOL_NAMES
TRAVERSAL_CONTEXT_PREFIX = structural_agent.TRAVERSAL_CONTEXT_PREFIX


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value

    if hasattr(value, "model_dump"):
        return value.model_dump(exclude_none=True)

    return dict(value)


def call_openrouter(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    require_tool: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        stream=False,
        **({"tools": tools} if tools else {}),
        **({"tool_choice": "required"} if tools and require_tool else {}),
    )
    usage = _as_dict(response.usage) if response.usage else {}
    return _as_dict(response.choices[0].message), usage


def progress_feedback(fn_name: str, args: dict[str, Any]) -> str:
    """Generate a prompt for the assistant to provide feedback on the current step."""
    if fn_name == "batch_search":
        ontology = args.get("ontologyId")
        suffix = f" in {ontology}" if ontology else ""
        return f'{FUNCTION_LABELS[fn_name]} for {args.get("query", [])}{suffix}'
    if fn_name == "ontologies_list":
        return FUNCTION_LABELS[fn_name]
    if fn_name in (
        "find_category_terms",
        "get_ontology_detail",
        "get_roots",
        "get_individuals",
    ):
        return f'{FUNCTION_LABELS[fn_name]} for "{args.get("ontologyId", "")}"'
    return f'{FUNCTION_LABELS[fn_name]} for "{args.get("iri", "")}"'


def _tool_allowed(fn_name: str, phase: str, response: dict[str, Any]) -> bool:
    if phase == "search":
        return (
            fn_name == "batch_search"
            and response["search_call_count"] < TERM_REQUEST_AGENT_MAX_INITIAL_SEARCH_CALLS
        )
    if response.get("pending_ontology_rejection_decision"):
        return False
    if response.get("allow_ontology_reselection"):
        return fn_name == "ontologies_list"
    if not response["ontologies_list_call_count"]:
        return fn_name == "ontologies_list"
    if response["available_ontology_ids"] and not response["selected_ontology_ids"]:
        return False
    return fn_name in TERM_REQUEST_TOOL_NAMES - {"ontologies_list"} or (
        fn_name == "ontologies_list" and response["allow_ontology_reselection"]
    )


def build_term_request_agent_input(
    label: str, definition: str, category: str, domain: str = ""
) -> str:
    return (
        f"Term label: {label}\n"
        f"Term definition: {definition}\n"
        f"Term category: {category}\n"
        f"Project domain: {domain}"
    )


def build_search_agent_input(description: str) -> str:
    return f"Search text: {description}"


def validate_search_agent_response(
    content: str, search_results: list[dict[str, Any]]
) -> tuple[bool, str, str]:
    try:
        response = json.loads(content)
    except (TypeError, json.JSONDecodeError):
        return False, "", "Return only a valid JSON object with up to five candidates."

    candidates = response.get("candidates") if isinstance(response, dict) else None
    if not isinstance(candidates, list) or len(candidates) > 5:
        return False, "", "Return a candidates list containing at most five terms."

    available = {
        (result["ontologyId"].casefold(), result["iri"]): result
        for result in search_results
    }
    normalized = []
    candidate_ids = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            return False, "", "Each candidate must be a JSON object."
        label = candidate.get("label")
        iri = candidate.get("iri")
        ontology_id = candidate.get("ontologyId") or candidate.get("ontology")
        if not all(isinstance(value, str) and value.strip() for value in (label, iri, ontology_id)):
            return False, "", "Each candidate must include label, iri, and ontologyId."
        candidate_id = (ontology_id.casefold(), iri)
        if candidate_id in candidate_ids:
            continue
        result = available.get(candidate_id)
        if result is None:
            return False, "", "Return only candidates provided by the batch_search function."
        candidate_ids.add(candidate_id)
        normalized.append(
            {
                "label": result["label"],
                "iri": result["iri"],
                "ontologyId": result["ontologyId"],
                "definition": (
                    result.get("definition", "")
                    if isinstance(result.get("definition", ""), str)
                    else ""
                ),
            }
        )

    response["candidates"] = normalized
    return True, json.dumps(response), ""


def validate_term_request_agent_response(
    content: str,
    selected_ontology_ids: list[str] | None = None,
    known_terms: list[dict[str, str]] | None = None,
) -> tuple[bool, str, str]:
    try:
        response = json.loads(content)
    except json.JSONDecodeError:
        return (
            False,
            "",
            "Your final response is not valid JSON. Return only a JSON object with exactly three candidates.",
        )

    if not isinstance(response, dict):
        return (
            False,
            "",
            "Your final response must be a JSON object with exactly three candidates.",
        )

    candidates = response.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 3:
        return False, "", "Your final response must include exactly three candidates."

    candidate_ids = set()
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            return False, "", "Each candidate must be a JSON object."
        parent_label = candidate.get("parent_label")
        parent_iri = candidate.get("parent_iri")
        ontology_id = (
            selected_ontology_ids[0]
            if selected_ontology_ids is not None and len(selected_ontology_ids) == 1
            else candidate.get("ontology") or candidate.get("ontologyId")
        )
        if not all(
            isinstance(value, str) and value
            for value in (parent_label, parent_iri, ontology_id)
        ):
            return (
                False,
                "",
                "Each candidate must include parent_label, parent_iri, and ontology.",
            )
        parent_label = parent_label.strip()
        ontology_id = ontology_id.strip()
        parent_iri = parent_iri.strip()
        if not parent_label or not ontology_id or not parent_iri:
            return (
                False,
                "",
                "Each candidate must include parent_label, parent_iri, and ontology.",
            )
        if selected_ontology_ids is not None and ontology_id not in selected_ontology_ids:
            return False, "", "Return candidates only from the selected ontologies."
        if known_terms is not None and not any(
            term.get("ontologyId") == ontology_id and term.get("iri") == parent_iri
            for term in known_terms
        ):
            return False, "", "Return candidates reached through the ontology traversal."
        candidate_id = (ontology_id.casefold(), parent_iri)
        if candidate_id in candidate_ids:
            return False, "", "Return three distinct candidates."
        candidate_ids.add(candidate_id)
        candidates[index] = {
            "parent_label": parent_label,
            "ontology": ontology_id,
            "parent_iri": parent_iri,
        }

    with ThreadPoolExecutor(max_workers=3) as executor:
        term_details = executor.map(
            get_term_detail,
            (candidate["parent_iri"] for candidate in candidates),
            (candidate["ontology"] for candidate in candidates),
        )
        for candidate, term_detail in zip(candidates, term_details):
            parent_iri = candidate["parent_iri"]
            ontology_id = candidate["ontology"]
            if (
                not isinstance(term_detail, dict)
                or term_detail.get("iri") != parent_iri
                or not isinstance(term_detail.get("label"), str)
                or not term_detail["label"].strip()
            ):
                return (
                    False,
                    "",
                    f"The parent term does not match ontology {ontology_id}: {parent_iri}. Continue searching and return an existing term.",
                )
            candidate["parent_label"] = term_detail["label"].strip()

    return True, json.dumps(response), ""


def validate_ontology_options(content, available_ontologies, rejected_ontology_ids=None):
    try:
        response = json.loads(content)
    except (TypeError, json.JSONDecodeError):
        return False, [], "Return only a valid JSON object with five ontology IDs."

    ontology_ids = response.get("ontologies") if isinstance(response, dict) else None
    rejected = set(rejected_ontology_ids or [])
    available = {
        ontology["ontologyId"]: ontology
        for ontology in available_ontologies
        if isinstance(ontology, dict)
        and isinstance(ontology.get("ontologyId"), str)
        and ontology["ontologyId"] not in rejected
    }
    expected_count = min(5, len(available))
    if (
        not isinstance(ontology_ids, list)
        or len(ontology_ids) != expected_count
        or len(set(ontology_ids)) != len(ontology_ids)
        or not all(isinstance(ontology_id, str) for ontology_id in ontology_ids)
    ):
        return False, [], f"Return exactly {expected_count} distinct ontology IDs."

    if any(ontology_id not in available for ontology_id in ontology_ids):
        return False, [], "Use only non-rejected ontology IDs returned by ontologies_list."
    return True, [available[ontology_id] for ontology_id in ontology_ids], ""


def _report_progress(response, message, progress_callback=None):
    response["progress_feedback"] = message
    if progress_callback:
        response["progress_emitted_live"] = True
        progress_callback(message)
    else:
        response["progress_feedbacks"].append(message)


def _require_ontology_list(messages, response):
    response["ontology_selection_failure_count"] = (
        response.get("ontology_selection_failure_count", 0) + 1
    )
    if response["ontology_selection_failure_count"] > MAX_ONTOLOGY_SELECTION_FAILURES:
        response["candidates"] = []
        response["error"] = "Assistant could not retrieve ontology metadata."
        response["is_final"] = True
        return
    response["force_tool_call"] = True
    messages.append(
        {
            "role": "user",
            "content": "Call ontologies_list now before returning a response.",
        }
    )


def run_term_request_or_search_agent_turn(
    messages, response, run_id=None, progress_callback=None
):
    response["progress_feedback"] = ""
    response["progress_feedbacks"] = []
    response["progress_emitted_live"] = False
    phase = response.get("phase", "term_request")
    if phase == "search":
        available_tools = search_agent.available_tools(
            TERM_REQUEST_SEARCH_TOOLS,
            response["search_call_count"],
            TERM_REQUEST_AGENT_MAX_INITIAL_SEARCH_CALLS,
        )
    else:
        structural_agent.initialize_state(response)
        structural_agent.update_traversal_context(messages, response)
        available_tools = [] if response["pending_ontology_rejection_decision"] else (
            structural_agent.available_tools(
                TERM_REQUEST_SEARCH_TOOLS,
                response["ontologies_list_call_count"],
                response["allow_ontology_reselection"],
                bool(response["available_ontology_ids"])
                and not response["selected_ontology_ids"],
            )
        )
    message, usage = call_openrouter(
        messages, available_tools, response.get("force_tool_call", False)
    )
    response["force_tool_call"] = False
    response["usage_stats"]["prompt_tokens"] += usage.get("prompt_tokens", 0)
    response["usage_stats"]["completion_tokens"] += usage.get("completion_tokens", 0)
    response["usage_stats"]["total_tokens"] += usage.get("total_tokens", 0)
    messages.append(message)
    if run_id:
        record_model_output(run_id, message, usage)

    tool_calls = message.get("tool_calls") or []
    if not tool_calls:
        content = message.get("content", "")
        try:
            assistant_response = json.loads(content)
        except (TypeError, json.JSONDecodeError):
            assistant_response = {}

        if phase == "term_request" and response["pending_ontology_rejection_decision"]:
            ontology_rejected = assistant_response.get("ontology_rejected")
            if not isinstance(ontology_rejected, bool):
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Return only JSON with ontology_rejected set to true or false. "
                            "Do not call a tool."
                        ),
                    }
                )
                return
            response["pending_ontology_rejection_decision"] = False
            response["allow_ontology_reselection"] = ontology_rejected
            response["force_tool_call"] = ontology_rejected
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Call ontologies_list now and rank five new ontology options."
                        if ontology_rejected
                        else "Keep the selected ontology and find different parent candidates within it."
                    ),
                }
            )
            return

        # A question pauses the worker so the next WebSocket user_message becomes
        # part of this same LLM conversation instead of starting another run.
        question = assistant_response.get("question")
        question_reason = assistant_response.get("reason")
        if isinstance(question, str) and question.strip():
            if response.get("phase", "term_request") != "term_request":
                messages.append(
                    {
                        "role": "user",
                        "content": "Do not ask questions. Use batch_search and return candidates.",
                    }
                )
                return
            if (
                not response["ontologies_list_call_count"]
                or (
                    response["available_ontology_ids"]
                    and not response["selected_ontology_ids"]
                )
            ):
                response["suppressed_domain_question_count"] = (
                    response.get("suppressed_domain_question_count", 0) + 1
                )
                if response["suppressed_domain_question_count"] > 1:
                    response["candidates"] = []
                    response["error"] = (
                        "Assistant did not select an ontology from the available metadata."
                    )
                    response["is_final"] = True
                    return
                response["force_tool_call"] = True
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Do not ask for domain information. Use the term label and "
                            "definition to select the closest ontology from the available "
                            "metadata, then continue."
                        ),
                    }
                )
                return
            if question_reason != "missing_context":
                response["invalid_question_reason_count"] = (
                    response.get("invalid_question_reason_count", 0) + 1
                )
                if response["invalid_question_reason_count"] > 1:
                    response["candidates"] = []
                    response["error"] = (
                        "Assistant could not classify its clarification request."
                    )
                    response["is_final"] = True
                    return
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Do not ask this question yet. Return it again with reason set "
                            "exactly to missing_context."
                        ),
                    }
                )
                return
            response["invalid_question_reason_count"] = 0
            if (
                response.get("clarification_count", 0)
                >= MAX_TERM_REQUEST_CLARIFICATIONS
            ):
                messages.append(
                    {
                        "role": "user",
                        "content": "Do not ask another question. Continue with the available information.",
                    }
                )
                return
            response["clarification_count"] = response.get("clarification_count", 0) + 1
            response["question"] = question
            response["needs_user_input"] = True
            return

        if phase == "search" and not response["successful_search_count"]:
            messages.append(
                {
                    "role": "user",
                    "content": "Use the batch_search function before returning candidates.",
                }
            )
            return

        if phase == "term_request" and not response["ontologies_list_call_count"]:
            _require_ontology_list(messages, response)
            return

        if (
            phase == "term_request"
            and response["available_ontology_ids"]
            and not response["selected_ontology_ids"]
        ):
            is_valid, options, feedback = validate_ontology_options(
                content,
                response["available_ontologies"],
                response["rejected_ontology_ids"],
            )
            if is_valid:
                if not options:
                    response["error"] = "No non-rejected ontologies are available."
                    response["is_final"] = True
                    return
                response["ontology_options"] = options
                response["needs_ontology_selection"] = True
                return
            messages.append({"role": "user", "content": feedback})
            return

        if phase == "search":
            is_valid, final_response, feedback = validate_search_agent_response(
                content, response["search_results"]
            )
        else:
            if response["term_category"] and not response["category_anchor_nodes"]:
                messages.append(
                    {
                        "role": "user",
                        "content": "Locate an exact category or category-synonym term before returning parent candidates.",
                    }
                )
                return
            is_valid, final_response, feedback = validate_term_request_agent_response(
                content,
                response["selected_ontology_ids"],
                response["known_terms"],
            )
        if is_valid:
            temp = json.loads(final_response)
            response["candidates"] = temp["candidates"]
            response["error"] = None
            response["is_final"] = True
            return

        messages.append(
            {
                "role": "user",
                "content": feedback,
            }
        )
        return

    for tool_call in tool_calls:
        response["progress_feedback"] = ""
        fn_name = tool_call["function"]["name"]
        args = tool_call["function"].get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args) if args else {}
            except json.JSONDecodeError:
                args = None

        if not isinstance(args, dict):
            result = {"error": "Function arguments must be a JSON object."}
        elif fn_name not in TERM_REQUEST_SEARCH_FUNCTIONS:
            result = {"error": f"Unknown function: {fn_name}"}
        elif not _tool_allowed(fn_name, phase, response):
            result = {
                "error": (
                    "ontologies_list can only be called once."
                    if phase == "term_request"
                    and fn_name == "ontologies_list"
                    and response["ontologies_list_call_count"]
                    else f"{fn_name} is not available for {phase}."
                )
            }
        else:
            response["is_final"] = False
            current_progress = progress_feedback(fn_name, args)
            _report_progress(response, current_progress, progress_callback)
            is_reselection = (
                phase == "term_request"
                and fn_name == "ontologies_list"
                and bool(response["rejected_ontology_ids"])
            )
            is_new_ontology = (
                phase == "term_request"
                and fn_name == "get_roots"
                and args.get("ontologyId") not in response["selected_ontology_ids"]
            )
            try:
                if phase == "search":
                    result = search_agent.execute_batch_search(
                        args,
                        response,
                        TERM_REQUEST_SEARCH_FUNCTIONS[fn_name],
                        TERM_REQUEST_AGENT_MAX_INITIAL_SEARCH_CALLS,
                    )
                else:
                    result = structural_agent.execute_tool(
                        fn_name, args, response, TERM_REQUEST_SEARCH_FUNCTIONS
                    )
            except Exception:
                logger.exception("AI assist tool %s failed", fn_name)
                result = {"error": "Unable to complete the ontology lookup."}

            if is_reselection:
                updated_progress = "Re-evaluating ontologies based on your feedback"
            elif is_new_ontology and args.get("ontologyId") in response["selected_ontology_ids"]:
                updated_progress = (
                    f'Selected ontology "{args["ontologyId"]}" and checking its root terms'
                )
            else:
                updated_progress = current_progress
            if updated_progress != current_progress:
                _report_progress(response, updated_progress, progress_callback)

            if fn_name == "ontologies_list" and result == []:
                response["candidates"] = []
                response["error"] = "No GitHub-hosted ontologies are available."
                response["is_final"] = True

        if isinstance(result, dict) and isinstance(result.get("error"), str):
            _report_progress(response, result["error"], progress_callback)
            if fn_name == "ontologies_list" and not response["available_ontology_ids"]:
                response["candidates"] = []
                response["error"] = result["error"]
                response["is_final"] = True

        messages.append(
            {
                "role": "tool",
                "content": json.dumps(result),
                "tool_call_id": tool_call["id"],
            }
        )
