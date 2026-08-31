from concurrent.futures import ThreadPoolExecutor
import json
import os
from typing import Any

from ai_assist.functions import (
    search,
    search_under_term,
    get_term_detail,
    get_term_children,
    get_ontology_detail,
    TOOLS,
)
from openai import OpenAI

from ai_assist.vars import MAX_INITIAL_SEARCH_CALLS

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["LLM_API_KEY"],
)
MODEL = os.environ["LLM_MODEL"]


FUNCTIONS = {
    "search": search,
    "get_term_detail": get_term_detail,
    "get_term_children": get_term_children,
    "get_ontology_detail": get_ontology_detail,
    "search_under_term": search_under_term,
}

FUNCTION_LABELS = {
    "search": "Searching terminology",
    "search_under_term": "Searching related terms",
    "get_term_detail": "Checking term details",
    "get_term_children": "Checking child terms",
    "get_ontology_detail": "Checking ontology details",
}


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
    """Run one non-streaming LLM turn and normalize the SDK objects for storage."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=tools,
        stream=False,
    )
    usage = _as_dict(response.usage) if response.usage else {}
    return _as_dict(response.choices[0].message), usage


def progress_feedback(fn_name: str, args: dict[str, Any]) -> str:
    if fn_name == "search":
        ontology = args.get("ontologyId")
        suffix = f" in {ontology}" if ontology else ""
        return f'{FUNCTION_LABELS[fn_name]} for "{args.get("query", "")}"{suffix}'
    if fn_name == "get_ontology_detail":
        return f'{FUNCTION_LABELS[fn_name]} for "{args.get("ontologyId", "")}"'
    return f'{FUNCTION_LABELS[fn_name]} for "{args.get("iri", "")}"'


def build_user_prompt(
    label: str, definition: str, category: str, domain: str = ""
) -> str:
    return (
        f"Term label: {label}\n"
        f"Term definition: {definition}\n"
        f"Term category: {category}\n"
        f"Project domain: {domain}"
    )


def validate_final_response(content: str) -> tuple[bool, str, str]:
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
            return False, "", "Each candidate must include parent_label, parent_iri, and ontology."
        parent_label = parent_label.strip()
        ontology_id = ontology_id.strip()
        parent_iri = parent_iri.strip()
        if not parent_label or not ontology_id or not parent_iri:
            return False, "", "Each candidate must include parent_label, parent_iri, and ontology."
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
            if isinstance(term_detail, str) and term_detail.startswith("Error:"):
                return (
                    False,
                    "",
                    f"The parent_iri does not exist in ontology {ontology_id}: {parent_iri}. Continue searching and return an existing term.",
                )

    return True, json.dumps(response), ""


def run_agent(messages, response):
    """Advance the LLM by one turn, including any requested terminology tools."""
    response["progress_feedback"] = ""
    available_tools = [
        tool
        for tool in TOOLS
        if response["search_call_count"] < MAX_INITIAL_SEARCH_CALLS
        or tool["function"]["name"] != "search"
    ]
    message, usage = call_openrouter(messages, available_tools)
    response["usage_stats"]["prompt_tokens"] += usage.get("prompt_tokens", 0)
    response["usage_stats"]["completion_tokens"] += usage.get("completion_tokens", 0)
    response["usage_stats"]["total_tokens"] += usage.get("total_tokens", 0)
    messages.append(message)

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
            response["question"] = question
            response["needs_user_input"] = True
            return

        is_valid, final_response, feedback = validate_final_response(content)
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
        elif fn_name not in FUNCTIONS:
            result = {"error": f"Unknown function: {fn_name}"}
        else:
            if fn_name == "search":
                response["search_call_count"] += 1
            if response["search_call_count"] > MAX_INITIAL_SEARCH_CALLS:
                result = {
                    "error": "Too many search calls. Use search_under_term instead."
                }
            else:
                response["is_final"] = False
                response["progress_feedback"] = progress_feedback(fn_name, args)
                try:
                    result = FUNCTIONS[fn_name](**args)
                except Exception as e:
                    result = {"error": str(e)}

        messages.append(
            {
                "role": "tool",
                "content": json.dumps(result),
                "tool_call_id": tool_call["id"],
            }
        )
