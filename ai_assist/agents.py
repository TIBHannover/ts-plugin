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
            "Your final response is not valid JSON. Return only a JSON object with parent_label, ontology, and parent_iri.",
        )

    if not isinstance(response, dict):
        return (
            False,
            "",
            "Your final response must be a JSON object with parent_label, ontology, and parent_iri.",
        )

    parent_iri = response.get("parent_iri")
    ontology_id = response.get("ontology") or response.get("ontologyId")
    if not parent_iri:
        return (
            False,
            "",
            "Your final response does not include parent_iri. Continue searching and return a valid existing parent_iri.",
        )
    if not ontology_id:
        return (
            False,
            "",
            "Your final response does not include ontology. Continue searching and return the ontology id for parent_iri.",
        )

    term_detail = get_term_detail(parent_iri, ontology_id)
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
        if response["search_call_count"] < 3 or tool["function"]["name"] != "search"
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
            response["parent_label"] = temp["parent_label"]
            response["ontology"] = temp["ontology"]
            response["parent_iri"] = temp["parent_iri"]
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
            if response["search_call_count"] > 3:
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
