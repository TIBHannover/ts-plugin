"""Structural ontology-traversal workflow helpers."""

import json
from typing import Any, Callable

TRAVERSAL_CONTEXT_PREFIX = "Ontology traversal state:"
MAX_CHILD_LOOKUP_ERRORS = 2
STRUCTURAL_TOOL_NAMES = {
    "add_parent_candidate",
    "ontologies_list",
    "get_ontology_detail",
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
    response.setdefault("candidate_parent_nodes", [])
    response.setdefault("candidate_parent_limit", 3)
    response.setdefault("child_lookup_errors", [])
    response.setdefault("unavailable_nodes", [])
    response.setdefault("rejected_parent_nodes", [])
    response.setdefault("visited_root_pages", [])
    response.setdefault("root_search_complete", {"class": False, "property": False})
    if not isinstance(response["root_search_complete"], dict):
        complete = bool(response["root_search_complete"])
        response["root_search_complete"] = {"class": complete, "property": complete}
    for term_type in ("class", "property"):
        response["root_search_complete"].setdefault(term_type, False)
    response.setdefault("visited_nodes", [])


def update_traversal_context(messages: list[dict[str, Any]], response: dict[str, Any]) -> None:
    content = (
        f"{TRAVERSAL_CONTEXT_PREFIX}\n"
        f"Requested term category: {response['term_category']}\n"
        f"Selected ontologies: {json.dumps(response['selected_ontology_ids'])}\n"
        f"Rejected ontologies: {json.dumps(response['rejected_ontology_ids'])}\n"
        f"Ontology reselection available: {json.dumps(response['allow_ontology_reselection'])}\n"
        f"Visited root pages: {json.dumps(response['visited_root_pages'])}\n"
        f"Root search complete: {json.dumps(response['root_search_complete'])}\n"
        f"Visited nodes: {json.dumps(response['visited_nodes'])}\n"
        f"Unavailable nodes: {json.dumps(response['unavailable_nodes'])}\n"
        f"Parent candidates ({len(response['candidate_parent_nodes'])}/{response['candidate_parent_limit']}): "
        f"{json.dumps(response['candidate_parent_nodes'])}\n"
        f"Rejected parent terms: {json.dumps(response['rejected_parent_nodes'])}\n"
        "Traverse root ancestors that can plausibly lead to the requested category, "
        "but every final parent must semantically be a type of that category. "
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
    names = (
        {"ontologies_list"}
        if allow_ontology_reselection
        else STRUCTURAL_TOOL_NAMES - {"ontologies_list"}
    )
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
    if function_name == "add_parent_candidate" and response["selected_ontology_ids"]:
        ontology_id = response["selected_ontology_ids"][0]
    node = {"ontologyId": ontology_id, "iri": arguments.get("iri")}
    root_page = {
        "ontologyId": ontology_id,
        "type": arguments.get("type"),
        "page": arguments.get("page", 0),
    }
    known_term = next(
        (
            term
            for term in response["known_terms"]
            if term["ontologyId"] == ontology_id and term["iri"] == arguments.get("iri")
        ),
        None,
    )
    validation_error = _validation_error(
        function_name, arguments, response, ontology_id, known_term, node, root_page
    )
    if validation_error:
        return {"error": validation_error}

    if function_name == "add_parent_candidate":
        candidate = {**node, "category_compatible": True}
        response["candidate_parent_nodes"].append(candidate)
        return candidate
    if function_name == "ontologies_list":
        arguments.clear()
        arguments["hosted_on_github"] = True
    result = functions[function_name](**arguments)
    if function_name == "search_in_children" and isinstance(result, str):
        return _record_child_lookup_error(response, node, result)
    _record_result(function_name, arguments, ontology_id, result, response, node, root_page)
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
    response["candidate_parent_nodes"] = []
    response["rejected_parent_nodes"] = []
    _reset_traversal(response)
    response["allow_ontology_reselection"] = False
    response["pending_ontology_rejection_decision"] = False
    response["ontology_selection_failure_count"] = 0
    response["suppressed_domain_question_count"] = 0
    response["invalid_question_reason_count"] = 0
    response["force_tool_call"] = False


def restart_parent_search(response):
    for candidate in response["candidates"]:
        node = {"ontologyId": candidate["ontology"], "iri": candidate["parent_iri"]}
        if not _contains_node(response["rejected_parent_nodes"], node):
            response["rejected_parent_nodes"].append(node)
    response["candidates"] = []
    response["known_terms"] = []
    response["candidate_parent_nodes"] = []
    _reset_traversal(response)


def _reset_traversal(response):
    response["visited_root_pages"] = []
    response["root_search_complete"] = {"class": False, "property": False}
    response["visited_nodes"] = []
    response["child_lookup_errors"] = []
    response["unavailable_nodes"] = []


def _validation_error(
    function_name, arguments, response, ontology_id, known_term, node, root_page
):
    if function_name == "ontologies_list":
        response["ontologies_list_call_count"] += 1
        return (
            "ontologies_list can only be called once."
            if response["ontologies_list_call_count"] > 1
            else None
        )
    if (
        response["selected_ontology_ids"]
        and ontology_id
        and ontology_id != response["selected_ontology_ids"][0]
    ):
        return f'Use the selected ontologyId "{response["selected_ontology_ids"][0]}" for all future tool calls.'
    if function_name in ("get_roots", "search_in_children") and not response[
        "ontologies_list_call_count"
    ]:
        return "Call ontologies_list before traversing ontologies."
    if function_name == "add_parent_candidate":
        if not response["selected_ontology_ids"]:
            return "Select an ontology before adding a parent candidate."
        if initial_root_types_remaining(response):
            return "Fetch page 0 for both class and property roots before adding candidates."
        if known_term is None:
            return "Add only a term returned by get_roots or search_in_children."
        if arguments.get("category_compatible") is not True:
            return "A parent candidate must semantically match the requested category."
        if _contains_node(response["candidate_parent_nodes"], node):
            return "This parent candidate has already been added."
        if _contains_node(response["rejected_parent_nodes"], node):
            return "A rejected parent term cannot be added again."
        if len(response["candidate_parent_nodes"]) >= response["candidate_parent_limit"]:
            return "The parent-candidate list is full."
        return None
    if function_name == "get_roots":
        if ontology_id not in response["available_ontology_ids"]:
            return "Select an ontology returned by ontologies_list."
        if ontology_id in response["rejected_ontology_ids"]:
            return f'Ontology "{ontology_id}" was rejected. Select the next closest ontology.'
        if ontology_id not in response["selected_ontology_ids"] and response[
            "selected_ontology_ids"
        ]:
            return "Only one ontology can be selected."
        if root_page in response["visited_root_pages"]:
            return "This ontology root page has already been visited."
        required_root_types = initial_root_types_remaining(response)
        if required_root_types and (
            arguments.get("page", 0) != 0
            or arguments.get("type") not in required_root_types
        ):
            return "Fetch page 0 for both class and property roots before continuing."
    if function_name == "search_in_children":
        if initial_root_types_remaining(response):
            return "Fetch page 0 for both class and property roots before traversing children."
        if ontology_id not in response["selected_ontology_ids"]:
            return "Call get_roots for this ontology first."
        if known_term is None:
            return "Select a term returned by get_roots or search_in_children."
        if arguments.get("term_type") != known_term.get("type"):
            return "term_type must match the selected term's type."
        if _contains_node(response["unavailable_nodes"], node):
            return "This ontology node is unavailable. Choose another returned term."
        if node in response["visited_nodes"]:
            return "This ontology node has already been visited."
    return None


def _record_result(
    function_name, arguments, ontology_id, result, response, node, root_page
):
    if isinstance(result, str):
        return
    if function_name == "ontologies_list" and isinstance(result, list):
        response["available_ontologies"] = result
        response["available_ontology_ids"] = [
            ontology["ontologyId"]
            for ontology in result
            if isinstance(ontology, dict)
            and isinstance(ontology.get("ontologyId"), str)
        ]
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
        response["root_search_complete"][arguments["type"]] = len(result) < 20
    if function_name == "search_in_children" and isinstance(result, (dict, list)):
        terms = result if isinstance(result, list) else [result]
        _record_known_terms(terms, ontology_id, response)
        response["visited_nodes"].append(node)
        response["child_lookup_errors"] = [
            error
            for error in response["child_lookup_errors"]
            if not _same_node(error, node)
        ]


def _record_known_terms(terms, ontology_id, response):
    for term in terms:
        if not isinstance(term, dict):
            continue
        known_term = {
            "ontologyId": ontology_id,
            "iri": term.get("iri"),
            "type": term.get("type"),
        }
        if all(isinstance(value, str) for value in known_term.values()) and known_term not in response[
            "known_terms"
        ]:
            response["known_terms"].append(known_term)


def _contains_node(nodes, node):
    return any(_same_node(item, node) for item in nodes)


def initial_root_types_remaining(response):
    visited = {
        page.get("type")
        for page in response["visited_root_pages"]
        if page.get("page") == 0
        and page.get("ontologyId") in response["selected_ontology_ids"]
    }
    return {"class", "property"} - visited


def _record_child_lookup_error(response, node, error):
    node_error = next(
        (item for item in response["child_lookup_errors"] if _same_node(item, node)),
        None,
    )
    if node_error:
        node_error["count"] += 1
    else:
        node_error = {**node, "count": 1}
        response["child_lookup_errors"].append(node_error)
    unavailable = node_error["count"] >= MAX_CHILD_LOOKUP_ERRORS
    if unavailable and not _contains_node(response["unavailable_nodes"], node):
        response["unavailable_nodes"].append(node)
    return {"error": error, "node_unavailable": unavailable}


def _same_node(left, right):
    return bool(
        left
        and right
        and left.get("ontologyId") == right.get("ontologyId")
        and left.get("iri") == right.get("iri")
    )
