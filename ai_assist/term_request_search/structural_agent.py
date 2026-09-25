"""Structural ontology-traversal workflow helpers."""

import json
from typing import Any, Callable

from .state import get_category_values


TRAVERSAL_CONTEXT_PREFIX = "Ontology traversal state:"
STRUCTURAL_TOOL_NAMES = {
    "ontologies_list",
    "get_ontology_detail",
    "find_category_terms",
    "get_roots",
    "search_in_children",
    "get_term_detail",
}


def initialize_state(response: dict[str, Any]) -> None:
    response.setdefault("term_category", "")
    response.setdefault("ontologies_list_call_count", 0)
    response.setdefault("available_ontology_ids", [])
    response.setdefault("available_ontologies", [])
    response.setdefault("ontology_options", [])
    response.setdefault("selected_ontology_ids", [])
    response.setdefault("rejected_ontology_ids", [])
    response.setdefault("allow_ontology_reselection", False)
    response.setdefault("pending_ontology_rejection_decision", False)
    response.setdefault("known_terms", [])
    response.setdefault("category_search_complete", False)
    response.setdefault("category_anchor_nodes", [])
    response.setdefault("category_branch_nodes", [])
    response.setdefault("visited_root_pages", [])
    response.setdefault("visited_nodes", [])
    response.setdefault("visited_node_pages", [])


def update_traversal_context(messages: list[dict[str, Any]], response: dict[str, Any]) -> None:
    content = (
        f"{TRAVERSAL_CONTEXT_PREFIX}\n"
        f"Requested term category: {response['term_category']}\n"
        f"Selected ontologies: {json.dumps(response['selected_ontology_ids'])}\n"
        f"Rejected ontologies: {json.dumps(response['rejected_ontology_ids'])}\n"
        f"Ontology reselection available: {json.dumps(response['allow_ontology_reselection'])}\n"
        f"Visited root pages: {json.dumps(response['visited_root_pages'])}\n"
        f"Visited nodes: {json.dumps(response['visited_nodes'])}\n"
        f"Visited node pages: {json.dumps(response['visited_node_pages'])}\n"
        f"Category search complete: {json.dumps(response['category_search_complete'])}\n"
        f"Category anchors: {json.dumps(response['category_anchor_nodes'])}\n"
        "The requested category is a hard subtree constraint. Locate its matching term before using the term label to descend. "
        "Do not request the same node again. Continue through terms returned by roots or child search."
    )
    for message in messages:
        if message.get("role") == "system" and message.get("content", "").startswith(
            TRAVERSAL_CONTEXT_PREFIX
        ):
            message["content"] = content
            return
    messages.insert(1 if messages else 0, {"role": "system", "content": content})


def available_tools(
    tools: list[dict[str, Any]],
    ontologies_list_call_count: int,
    allow_ontology_reselection: bool = False,
    ontology_selection_required: bool = False,
):
    if not ontologies_list_call_count:
        return [tool for tool in tools if tool["function"]["name"] == "ontologies_list"]
    if ontology_selection_required:
        return []
    names = {"ontologies_list"} if allow_ontology_reselection else STRUCTURAL_TOOL_NAMES - {"ontologies_list"}
    return [tool for tool in tools if tool["function"]["name"] in names]


def execute_tool(
    function_name: str,
    arguments: dict[str, Any],
    response: dict[str, Any],
    functions: dict[str, Callable[..., Any]],
) -> Any:
    if response["allow_ontology_reselection"]:
        if function_name == "ontologies_list":
            restart_ontology_selection(response)
        else:
            response["allow_ontology_reselection"] = False
    ontology_id = arguments.get("ontologyId")
    node = {"ontologyId": ontology_id, "iri": arguments.get("iri")}
    node_page = {**node, "page": arguments.get("page", 0)}
    root_page = {"ontologyId": ontology_id, "type": arguments.get("type"), "page": arguments.get("page", 0)}
    known_term = next((term for term in response["known_terms"] if term["ontologyId"] == ontology_id and term["iri"] == arguments.get("iri")), None)
    validation_error = _validation_error(
        function_name, arguments, response, ontology_id, known_term, node, node_page, root_page
    )
    if validation_error:
        return {"error": validation_error}

    if function_name == "ontologies_list":
        arguments.clear()
        arguments["hosted_on_github"] = True
    if function_name == "find_category_terms":
        arguments["category"] = response["term_category"]
    result = functions[function_name](**arguments)
    _record_result(function_name, ontology_id, result, response, node, node_page, root_page)
    return result


def restart_ontology_selection(response):
    for ontology_id in response["selected_ontology_ids"]:
        if ontology_id not in response["rejected_ontology_ids"]:
            response["rejected_ontology_ids"].append(ontology_id)
    response["ontologies_list_call_count"] = 0
    response["available_ontology_ids"] = []
    response["available_ontologies"] = []
    response["ontology_options"] = []
    response["selected_ontology_ids"] = []
    response["known_terms"] = []
    response["category_search_complete"] = False
    response["category_anchor_nodes"] = []
    response["category_branch_nodes"] = []
    response["visited_root_pages"] = []
    response["visited_nodes"] = []
    response["visited_node_pages"] = []
    response["allow_ontology_reselection"] = False
    response["pending_ontology_rejection_decision"] = False
    response["ontology_selection_failure_count"] = 0
    response["suppressed_domain_question_count"] = 0
    response["invalid_question_reason_count"] = 0
    response["force_tool_call"] = False


def _validation_error(function_name, arguments, response, ontology_id, known_term, node, node_page, root_page):
    if function_name == "ontologies_list":
        response["ontologies_list_call_count"] += 1
        return "ontologies_list can only be called once." if response["ontologies_list_call_count"] > 1 else None
    if (
        response["selected_ontology_ids"]
        and ontology_id
        and ontology_id != response["selected_ontology_ids"][0]
    ):
        return f'Use the selected ontologyId "{response["selected_ontology_ids"][0]}" for all future tool calls.'
    if function_name in ("get_roots", "search_in_children") and not response["ontologies_list_call_count"]:
        return "Call ontologies_list before traversing ontologies."
    if function_name == "find_category_terms":
        if ontology_id not in response["selected_ontology_ids"]:
            return "Select an ontology before searching for the category."
        if response["category_search_complete"]:
            return "The requested category has already been searched."
    if (
        function_name in ("get_roots", "search_in_children")
        and response["selected_ontology_ids"]
        and response["term_category"]
        and not response["category_search_complete"]
    ):
        return "Call find_category_terms before traversing the ontology."
    if function_name == "get_roots":
        if response["category_anchor_nodes"]:
            return "Start traversal from a category term returned by find_category_terms."
        if ontology_id not in response["available_ontology_ids"]:
            return "Select an ontology returned by ontologies_list."
        if ontology_id in response["rejected_ontology_ids"]:
            return f'Ontology "{ontology_id}" was rejected. Select the next closest ontology.'
        if ontology_id not in response["selected_ontology_ids"] and response["selected_ontology_ids"]:
            return "Only one ontology can be selected."
        if root_page in response["visited_root_pages"]:
            return "This ontology root page has already been visited."
    if function_name == "search_in_children":
        if ontology_id not in response["selected_ontology_ids"]:
            return "Call get_roots for this ontology first."
        if known_term is None:
            return "Select a term returned by get_roots or search_in_children."
        if (
            response["category_anchor_nodes"]
            and node not in response["category_branch_nodes"]
        ):
            return "Traverse only from the category anchors or their descendants."
        if (
            not response["category_anchor_nodes"]
            and response["term_category"]
            and arguments.get("query", "").strip().casefold()
            not in {
                value.casefold()
                for value in get_category_values(response["term_category"])
            }
        ):
            return "Use the category or one of its synonyms until its subtree is found."
        if arguments.get("term_type") != known_term.get("type"):
            return "term_type must match the selected term's type."
        if node in response["visited_nodes"]:
            return "This ontology node has already been visited."
    return None


def _record_result(function_name, ontology_id, result, response, node, node_page, root_page):
    if isinstance(result, str):
        return
    if function_name == "ontologies_list" and isinstance(result, list):
        response["available_ontologies"] = result
        response["available_ontology_ids"] = [ontology["ontologyId"] for ontology in result if isinstance(ontology, dict) and isinstance(ontology.get("ontologyId"), str)]
        response["suppressed_domain_question_count"] = 0
        if response["available_ontology_ids"]:
            response["ontology_selection_failure_count"] = 0
    if function_name == "get_roots" and ontology_id not in response["selected_ontology_ids"]:
        response["selected_ontology_ids"].append(ontology_id)
        response["suppressed_domain_question_count"] = 0
    if function_name == "get_roots":
        response["visited_root_pages"].append(root_page)
    if function_name == "get_roots" and isinstance(result, list):
        _record_known_terms(result, ontology_id, response)
        for term in result:
            if _matches_category(term, response["term_category"]):
                _record_category_anchor(term, ontology_id, response)
    if function_name == "find_category_terms" and isinstance(result, dict):
        response["category_search_complete"] = True
        terms = [
            term
            for matches in result.values()
            if isinstance(matches, list)
            for term in matches
        ]
        _record_known_terms(terms, ontology_id, response)
        for term in terms:
            _record_category_anchor(term, ontology_id, response)
    if function_name == "search_in_children":
        if isinstance(result, dict):
            _record_known_terms([result], ontology_id, response)
            child = {"ontologyId": ontology_id, "iri": result.get("iri")}
            if not response["category_anchor_nodes"] and _matches_category(
                result, response["term_category"]
            ):
                _record_category_anchor(result, ontology_id, response)
            elif (
                response["category_anchor_nodes"]
                and isinstance(child["iri"], str)
                and child not in response["category_branch_nodes"]
            ):
                response["category_branch_nodes"].append(child)
        if node not in response["visited_nodes"]:
            response["visited_nodes"].append(node)


def _record_known_terms(terms, ontology_id, response):
    for term in terms:
        if not isinstance(term, dict):
            continue
        known_term = {"ontologyId": ontology_id, "iri": term.get("iri"), "type": term.get("type")}
        if all(isinstance(value, str) for value in known_term.values()) and known_term not in response["known_terms"]:
            response["known_terms"].append(known_term)


def _matches_category(term, category):
    category_values = {value.casefold() for value in get_category_values(category)}
    return any(
        value.strip().casefold() in category_values
        for value in _text_values(term.get("label", ""))
        + _text_values(term.get("synonym", []))
    )


def _record_category_anchor(term, ontology_id, response):
    anchor = {"ontologyId": ontology_id, "iri": term.get("iri")}
    if isinstance(anchor["iri"], str) and anchor not in response["category_anchor_nodes"]:
        response["category_anchor_nodes"].append(anchor)
        response["category_branch_nodes"].append(anchor)


def _text_values(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []
