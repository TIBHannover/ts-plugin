"""Structural ontology-traversal workflow helpers."""

import json
from typing import Any, Callable


TRAVERSAL_CONTEXT_PREFIX = "Ontology traversal state:"
STRUCTURAL_TOOL_NAMES = {
    "ontologies_list",
    "get_ontology_detail",
    "get_roots",
    "get_term_children",
    "get_term_detail",
}


def initialize_state(response: dict[str, Any]) -> None:
    response.setdefault("ontologies_list_call_count", 0)
    response.setdefault("available_ontology_ids", [])
    response.setdefault("selected_ontology_ids", [])
    response.setdefault("known_terms", [])
    response.setdefault("visited_root_pages", [])
    response.setdefault("visited_nodes", [])
    response.setdefault("visited_node_pages", [])


def update_traversal_context(messages: list[dict[str, Any]], response: dict[str, Any]) -> None:
    content = (
        f"{TRAVERSAL_CONTEXT_PREFIX}\n"
        f"Selected ontologies: {json.dumps(response['selected_ontology_ids'])}\n"
        f"Visited root pages: {json.dumps(response['visited_root_pages'])}\n"
        f"Visited nodes: {json.dumps(response['visited_nodes'])}\n"
        f"Visited node pages: {json.dumps(response['visited_node_pages'])}\n"
        "Do not request the same node page again. Continue through terms returned by roots or children."
    )
    for message in messages:
        if message.get("role") == "system" and message.get("content", "").startswith(
            TRAVERSAL_CONTEXT_PREFIX
        ):
            message["content"] = content
            return
    messages.insert(1 if messages else 0, {"role": "system", "content": content})


def available_tools(tools: list[dict[str, Any]], ontologies_list_call_count: int):
    if not ontologies_list_call_count:
        return [tool for tool in tools if tool["function"]["name"] == "ontologies_list"]
    return [tool for tool in tools if tool["function"]["name"] in STRUCTURAL_TOOL_NAMES - {"ontologies_list"}]


def execute_tool(
    function_name: str,
    arguments: dict[str, Any],
    response: dict[str, Any],
    functions: dict[str, Callable[..., Any]],
) -> Any:
    ontology_id = arguments.get("ontologyId")
    node = {"ontologyId": ontology_id, "iri": arguments.get("iri")}
    node_page = {**node, "page": arguments.get("page", 0)}
    root_page = {"ontologyId": ontology_id, "type": arguments.get("type"), "page": arguments.get("page", 0)}
    known_term = next((term for term in response["known_terms"] if term["ontologyId"] == ontology_id and term["iri"] == arguments.get("iri")), None)
    validation_error = _validation_error(
        function_name, arguments, response, ontology_id, known_term, node_page, root_page
    )
    if validation_error:
        return {"error": validation_error}

    if function_name == "ontologies_list":
        arguments["hosted_on_github"] = True
    result = functions[function_name](**arguments)
    _record_result(function_name, ontology_id, result, response, node, node_page, root_page)
    return result


def _validation_error(function_name, arguments, response, ontology_id, known_term, node_page, root_page):
    if function_name == "ontologies_list":
        response["ontologies_list_call_count"] += 1
        return "ontologies_list can only be called once." if response["ontologies_list_call_count"] > 1 else None
    if function_name in ("get_roots", "get_term_children") and not response["ontologies_list_call_count"]:
        return "Call ontologies_list before traversing ontologies."
    if function_name == "get_roots":
        if ontology_id not in response["available_ontology_ids"]:
            return "Select an ontology returned by ontologies_list."
        if ontology_id not in response["selected_ontology_ids"] and len(response["selected_ontology_ids"]) >= 3:
            return "At most three ontologies can be selected."
        if root_page in response["visited_root_pages"]:
            return "This ontology root page has already been visited."
    if function_name == "get_term_children":
        if ontology_id not in response["selected_ontology_ids"]:
            return "Call get_roots for this ontology first."
        if known_term is None:
            return "Select a term returned by get_roots or get_term_children."
        if arguments.get("term_type") != known_term.get("type"):
            return "term_type must match the selected term's type."
        if node_page in response["visited_node_pages"]:
            return "This ontology node page has already been visited."
    return None


def _record_result(function_name, ontology_id, result, response, node, node_page, root_page):
    if isinstance(result, str):
        return
    if function_name == "ontologies_list" and isinstance(result, list):
        response["available_ontology_ids"] = [ontology["ontologyId"] for ontology in result if isinstance(ontology, dict) and isinstance(ontology.get("ontologyId"), str)]
    if function_name == "get_roots" and ontology_id not in response["selected_ontology_ids"]:
        response["selected_ontology_ids"].append(ontology_id)
    if function_name == "get_roots":
        response["visited_root_pages"].append(root_page)
    if function_name in ("get_roots", "get_term_children") and isinstance(result, list):
        _record_known_terms(result, ontology_id, response)
    if function_name == "get_term_children":
        if node not in response["visited_nodes"]:
            response["visited_nodes"].append(node)
        response["visited_node_pages"].append(node_page)


def _record_known_terms(terms, ontology_id, response):
    for term in terms:
        if not isinstance(term, dict):
            continue
        known_term = {"ontologyId": term.get("ontologyId", ontology_id), "iri": term.get("iri"), "type": term.get("type")}
        if all(isinstance(value, str) for value in known_term.values()) and known_term not in response["known_terms"]:
            response["known_terms"].append(known_term)
