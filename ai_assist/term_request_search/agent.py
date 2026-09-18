from concurrent.futures import ThreadPoolExecutor
import json
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

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["LLM_API_KEY"],
)
MODEL = os.environ["LLM_MODEL"]
MAX_TERM_REQUEST_CLARIFICATIONS = 2


FUNCTION_LABELS = {
    "batch_search": "Searching terminology",
    "search_under_term": "Searching related terms",
    "get_term_detail": "Checking term details",
    "get_term_children": "Checking child terms",
    "get_roots": "Checking root terms",
    "get_individuals": "Checking individuals",
    "get_ontology_detail": "Checking ontology details",
    "ontologies_list": "Listing ontologies",
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
) -> tuple[dict[str, Any], dict[str, Any]]:
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        stream=False,
        **({"tools": tools} if tools else {}),
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
    if fn_name in ("get_ontology_detail", "get_roots", "get_individuals"):
        return f'{FUNCTION_LABELS[fn_name]} for "{args.get("ontologyId", "")}"'
    return f'{FUNCTION_LABELS[fn_name]} for "{args.get("iri", "")}"'


def _tool_allowed(fn_name: str, phase: str, response: dict[str, Any]) -> bool:
    if phase == "search":
        return (
            fn_name == "batch_search"
            and response["search_call_count"] < TERM_REQUEST_AGENT_MAX_INITIAL_SEARCH_CALLS
        )
    if not response["ontologies_list_call_count"]:
        return fn_name == "ontologies_list"
    return fn_name in TERM_REQUEST_TOOL_NAMES - {"ontologies_list"}


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
    visited_nodes: list[dict[str, str]] | None = None,
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
        ontology_id = candidate.get("ontology") or candidate.get("ontologyId")
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
        if visited_nodes is not None and not any(
            node.get("ontologyId") == ontology_id and node.get("iri") == parent_iri
            for node in visited_nodes
        ):
            return False, "", "Inspect each candidate's children before returning it."
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
                or term_detail.get("ontologyId") != ontology_id
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


def run_term_request_or_search_agent_turn(messages, response, run_id=None):
    response["progress_feedback"] = ""
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
        available_tools = structural_agent.available_tools(
            TERM_REQUEST_SEARCH_TOOLS, response["ontologies_list_call_count"]
        )
    message, usage = call_openrouter(messages, available_tools)
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

        # A question pauses the worker so the next WebSocket user_message becomes
        # part of this same LLM conversation instead of starting another run.
        question = assistant_response.get("question")
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

        if phase == "search":
            is_valid, final_response, feedback = validate_search_agent_response(
                content, response["search_results"]
            )
        else:
            is_valid, final_response, feedback = validate_term_request_agent_response(
                content,
                response["selected_ontology_ids"],
                response["known_terms"],
                response["visited_nodes"],
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
            response["progress_feedback"] = progress_feedback(fn_name, args)
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
            except Exception as error:
                result = {"error": str(error)}

        messages.append(
            {
                "role": "tool",
                "content": json.dumps(result),
                "tool_call_id": tool_call["id"],
            }
        )
