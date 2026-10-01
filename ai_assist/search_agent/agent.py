"""Normal terminology-search workflow helpers."""

import json
from typing import Any, Callable

from ai_assist.functions import TOOLS, batch_search
from ai_assist.model_client import call_openrouter
from ai_assist.session_logging import record_model_output

MAX_SEARCH_CALLS = 3


def build_input(description: str) -> str:
    return f"Search text: {description}"


def validate_response(
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
        if not all(
            isinstance(value, str) and value.strip()
            for value in (label, iri, ontology_id)
        ):
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
                "definition": result.get("definition", "")
                if isinstance(result.get("definition", ""), str)
                else "",
            }
        )

    response["candidates"] = normalized
    return True, json.dumps(response), ""


def available_tools(tools: list[dict[str, Any]], search_call_count: int, max_calls: int):
    if search_call_count >= max_calls:
        return []
    return [tool for tool in tools if tool["function"]["name"] == "batch_search"]


def execute_batch_search(
    arguments: dict[str, Any],
    response: dict[str, Any],
    batch_search: Callable[..., Any],
    max_calls: int,
) -> Any:
    response["search_call_count"] += 1
    if response["search_call_count"] > max_calls:
        return {"error": "Too many batch_search calls. Use other available tools."}

    arguments["excludeCandidates"] = response["excluded_search_candidates"]
    result = batch_search(**arguments)
    if isinstance(result, dict):
        response["successful_search_count"] += 1
        response["search_results"].extend(
            candidate
            for query_results in result.values()
            if isinstance(query_results, list)
            for candidate in query_results
        )
    return result


def final_response_feedback(successful_search_count: int) -> str | None:
    if successful_search_count:
        return None
    return "Use the batch_search function before returning candidates."


def run_agent_turn(messages, response, run_id=None, progress_callback=None):
    response["progress_feedback"] = ""
    response["progress_feedbacks"] = []
    response["progress_emitted_live"] = False
    tools = available_tools(TOOLS, response["search_call_count"], MAX_SEARCH_CALLS)
    message, usage = call_openrouter(messages, tools)
    _record_usage(response, usage)
    messages.append(message)
    if run_id:
        record_model_output(run_id, message, usage)

    tool_calls = message.get("tool_calls") or []
    if not tool_calls:
        _handle_final_response(messages, response, message.get("content", ""))
        return

    response["invalid_final_response_count"] = 0
    for tool_call in tool_calls:
        _handle_tool_call(tool_call, messages, response, progress_callback)


def _record_usage(response, usage):
    for name in ("prompt_tokens", "completion_tokens", "total_tokens"):
        response["usage_stats"][name] += usage.get(name, 0)


def _handle_final_response(messages, response, content):
    if not response["successful_search_count"]:
        messages.append(
            {"role": "user", "content": "Use the batch_search function before returning candidates."}
        )
        return
    is_valid, final_response, feedback = validate_response(
        content, response["search_results"]
    )
    if is_valid:
        response["candidates"] = json.loads(final_response)["candidates"]
        response["error"] = None
        response["is_final"] = True
        return
    response["invalid_final_response_count"] += 1
    if response["invalid_final_response_count"] >= 2:
        response["candidates"] = []
        response["error"] = "Assistant could not produce a valid parent-term result."
        response["is_final"] = True
        return
    messages.append({"role": "user", "content": feedback})


def _handle_tool_call(tool_call, messages, response, progress_callback):
    function_name = tool_call["function"]["name"]
    arguments = _parse_arguments(tool_call["function"].get("arguments", {}))
    if not isinstance(arguments, dict):
        result = {"error": "Function arguments must be a JSON object."}
    elif function_name != "batch_search":
        result = {"error": f"{function_name} is not available for search."}
    else:
        _report_progress(response, "Searching terminology", progress_callback)
        try:
            result = execute_batch_search(
                arguments, response, batch_search, MAX_SEARCH_CALLS
            )
        except Exception:
            result = {"error": "Unable to complete the ontology lookup."}
    if isinstance(result, dict) and isinstance(result.get("error"), str):
        _report_progress(response, result["error"], progress_callback)
    messages.append(
        {"role": "tool", "content": json.dumps(result), "tool_call_id": tool_call["id"]}
    )


def _parse_arguments(arguments):
    if not isinstance(arguments, str):
        return arguments
    try:
        return json.loads(arguments) if arguments else {}
    except json.JSONDecodeError:
        return None


def _report_progress(response, message, progress_callback):
    response["progress_feedback"] = message
    if progress_callback:
        response["progress_emitted_live"] = True
        progress_callback(message)
    else:
        response["progress_feedbacks"].append(message)
