"""Normal terminology-search workflow helpers."""

from typing import Any, Callable


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
