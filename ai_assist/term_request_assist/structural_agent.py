"""Structural ontology-traversal workflow helpers."""

import json
from typing import Any, Callable

TRAVERSAL_CONTEXT_PREFIX = "Ontology traversal state:"
MAX_BEAM_NODE_ERRORS = 2
BEAM_WIDTH = 3
STRUCTURAL_TOOL_NAMES = {
    "ontologies_list",
    "get_ontology_detail",
    "select_beam_subtrees",
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
    response.setdefault("beam_frontier_nodes", [])
    response.setdefault("beam_option_nodes", [])
    response.setdefault("beam_terminal_nodes", [])
    response.setdefault("beam_fallback_nodes", [])
    response.setdefault("expanded_beam_nodes", [])
    response.setdefault("rejected_parent_nodes", [])
    response.setdefault("beam_options_classified", False)
    response.setdefault("beam_node_errors", [])
    response.setdefault("visited_root_pages", [])
    response.setdefault("root_search_complete", {"class": False, "property": False})
    if not isinstance(response["root_search_complete"], dict):
        complete = bool(response["root_search_complete"])
        response["root_search_complete"] = {
            "class": complete,
            "property": complete,
        }
    for term_type in ("class", "property"):
        response["root_search_complete"].setdefault(term_type, False)
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
        f"Root search complete: {json.dumps(response['root_search_complete'])}\n"
        f"Visited nodes: {json.dumps(response['visited_nodes'])}\n"
        f"Visited node pages: {json.dumps(response['visited_node_pages'])}\n"
        f"Active beam: {json.dumps(response['beam_frontier_nodes'])}\n"
        f"Beam option count: {len(response['beam_option_nodes'])}\n"
        f"Terminal parents: {json.dumps(response['beam_terminal_nodes'])}\n"
        f"Exhausted branch fallbacks: {json.dumps(response['beam_fallback_nodes'])}\n"
        f"Rejected parent terms: {json.dumps(response['rejected_parent_nodes'])}\n"
        f"Beam options classified: {json.dumps(response['beam_options_classified'])}\n"
        f"Beam lookup errors: {json.dumps(response['beam_node_errors'])}\n"
        "Traverse root ancestors that can plausibly lead to the requested category, but every final parent must semantically be a type of that category. "
        "Fill the remaining three-slot beam with the best suitable active or terminal options. Terminal parents persist and do not need to be selected again. "
        "Continue until three terminal parents are collected or no suitable active branch remains. "
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
    if function_name == "select_beam_subtrees":
        options = {
            option["iri"]: option
            for option in response["beam_option_nodes"]
            if option["ontologyId"] == response["selected_ontology_ids"][0]
        }
        classified = {item["iri"]: item["status"] for item in arguments["options"]}
        category_compatible = {
            item["iri"]: item["category_compatible"] for item in arguments["options"]
        }
        nodes = [options[iri] for iri in classified]
        for terminal in (
            node for node in nodes if classified[node["iri"]] == "terminal"
        ):
            terminal = {
                **terminal,
                "category_compatible": category_compatible[terminal["iri"]],
            }
            if not _contains_node(response["beam_terminal_nodes"], terminal):
                response["beam_terminal_nodes"].append(terminal)
        response["beam_terminal_nodes"] = response["beam_terminal_nodes"][:BEAM_WIDTH]
        remaining_slots = BEAM_WIDTH - len(response["beam_terminal_nodes"])
        response["beam_frontier_nodes"] = [
            {
                **node,
                "category_compatible": category_compatible[node["iri"]],
            }
            for node in nodes
            if classified[node["iri"]] == "active"
        ][:remaining_slots]
        for option in options.values():
            if (
                option["iri"] not in classified
                and _contains_node(response["expanded_beam_nodes"], option)
                and any(
                    node.get("parent_iri") == option["iri"] for node in nodes
                )
                and not _contains_node(response["rejected_parent_nodes"], option)
                and not _contains_node(response["beam_fallback_nodes"], option)
            ):
                response["beam_fallback_nodes"].append(option)
        response["beam_fallback_nodes"] = sorted(
            response["beam_fallback_nodes"],
            key=lambda option: option.get("depth", 0),
            reverse=True,
        )[:BEAM_WIDTH]
        response["beam_option_nodes"] = response["beam_frontier_nodes"].copy()
        response["beam_options_classified"] = True
        return nodes
    result = functions[function_name](**arguments)
    if function_name == "search_in_children" and isinstance(result, str):
        return _record_beam_error(response, node, result)
    _record_result(
        function_name, arguments, ontology_id, result, response, node, node_page, root_page
    )
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
    response["beam_frontier_nodes"] = []
    response["beam_option_nodes"] = []
    response["beam_terminal_nodes"] = []
    response["beam_fallback_nodes"] = []
    response["expanded_beam_nodes"] = []
    response["rejected_parent_nodes"] = []
    response["beam_options_classified"] = False
    response["beam_node_errors"] = []
    response["visited_root_pages"] = []
    response["root_search_complete"] = {"class": False, "property": False}
    response["visited_nodes"] = []
    response["visited_node_pages"] = []
    response["allow_ontology_reselection"] = False
    response["pending_ontology_rejection_decision"] = False
    response["ontology_selection_failure_count"] = 0
    response["suppressed_domain_question_count"] = 0
    response["invalid_question_reason_count"] = 0
    response["force_tool_call"] = False


def restart_parent_search(response):
    for candidate in response["candidates"]:
        node = {
            "ontologyId": candidate["ontology"],
            "iri": candidate["parent_iri"],
        }
        if not _contains_node(response["rejected_parent_nodes"], node):
            response["rejected_parent_nodes"].append(node)
    response["candidates"] = []
    response["known_terms"] = []
    response["beam_frontier_nodes"] = []
    response["beam_option_nodes"] = []
    response["beam_terminal_nodes"] = []
    response["beam_fallback_nodes"] = []
    response["expanded_beam_nodes"] = []
    response["beam_options_classified"] = False
    response["beam_node_errors"] = []
    response["visited_root_pages"] = []
    response["root_search_complete"] = {"class": False, "property": False}
    response["visited_nodes"] = []
    response["visited_node_pages"] = []


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
    if function_name == "select_beam_subtrees":
        classifications = arguments.get("options")
        if (
            not isinstance(classifications, list)
            or not classifications
            or len(classifications)
            > BEAM_WIDTH - len(response["beam_terminal_nodes"])
            or not all(
                isinstance(item, dict)
                and isinstance(item.get("iri"), str)
                and item["iri"]
                and item.get("status") in ("active", "terminal")
                and isinstance(item.get("category_compatible"), bool)
                for item in classifications
            )
        ):
            return "Select only enough beam options to fill the remaining three-slot beam."
        if not response["selected_ontology_ids"]:
            return "Select an ontology before selecting beam subtrees."
        iris = [item["iri"] for item in classifications]
        expected_iris = {node["iri"] for node in response["beam_option_nodes"]}
        if len(set(iris)) != len(iris) or not set(iris) <= expected_iris:
            return "Select only distinct current beam options."
        for item in classifications:
            node = {
                "ontologyId": response["selected_ontology_ids"][0],
                "iri": item["iri"],
            }
            if item["status"] == "terminal" and not _contains_node(
                response["expanded_beam_nodes"], node
            ):
                return "Only an expanded beam node can be marked terminal."
            if item["status"] == "terminal" and not item["category_compatible"]:
                return "A terminal parent must semantically be a type of the requested category."
            if item["status"] == "terminal" and _contains_node(
                response["rejected_parent_nodes"], node
            ):
                return "A rejected parent term cannot be selected again."
            if item["status"] == "active" and _contains_node(
                response["visited_nodes"], node
            ):
                return "An expanded beam node must be terminal or discarded."
        return None
    if function_name == "get_roots":
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
        if not _contains_node(response["beam_frontier_nodes"], node):
            return "Call select_beam_subtrees and expand only an active beam node."
        if arguments.get("term_type") != known_term.get("type"):
            return "term_type must match the selected term's type."
        if node in response["visited_nodes"]:
            return "This ontology node has already been visited."
    return None


def _record_result(
    function_name, arguments, ontology_id, result, response, node, node_page, root_page
):
    if isinstance(result, str):
        return
    if function_name == "search_in_children" and not _contains_node(
        response["expanded_beam_nodes"], node
    ):
        response["expanded_beam_nodes"].append(node)
    if function_name == "search_in_children":
        response["beam_node_errors"] = [
            error
            for error in response["beam_node_errors"]
            if not _same_node(error, node)
        ]
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
        response["root_search_complete"][arguments["type"]] = len(result) < 20
        if result:
            _record_beam_options(result, ontology_id, response)
        else:
            response["beam_options_classified"] = True
    if function_name == "search_in_children" and isinstance(result, (dict, list)):
        terms = result if isinstance(result, list) else [result]
        _record_known_terms(terms, ontology_id, response)
        _record_beam_options(terms, ontology_id, response, node)
        if node not in response["visited_nodes"]:
            response["visited_nodes"].append(node)


def _record_known_terms(terms, ontology_id, response):
    for term in terms:
        if not isinstance(term, dict):
            continue
        known_term = {"ontologyId": ontology_id, "iri": term.get("iri"), "type": term.get("type")}
        if all(isinstance(value, str) for value in known_term.values()) and known_term not in response["known_terms"]:
            response["known_terms"].append(known_term)


def _record_beam_options(terms, ontology_id, response, parent=None):
    response["beam_options_classified"] = False
    for term in terms:
        node = {
            "ontologyId": ontology_id,
            "iri": term.get("iri"),
        }
        if parent:
            node["parent_iri"] = parent["iri"]
            node["depth"] = next(
                (
                    item.get("depth", 0) + 1
                    for item in response["beam_frontier_nodes"]
                    if _same_node(item, parent)
                ),
                1,
            )
        if not isinstance(node["iri"], str):
            continue
        if not _contains_node(response["beam_option_nodes"], node):
            response["beam_option_nodes"].append(node)


def _record_beam_error(response, node, error):
    node_error = next(
        (item for item in response["beam_node_errors"] if _same_node(item, node)),
        None,
    )
    if node_error:
        node_error["count"] += 1
    else:
        node_error = {**node, "count": 1}
        response["beam_node_errors"].append(node_error)
    discarded = node_error["count"] >= MAX_BEAM_NODE_ERRORS
    if discarded:
        response["beam_frontier_nodes"] = [
            item
            for item in response["beam_frontier_nodes"]
            if not _same_node(item, node)
        ]
        response["beam_option_nodes"] = [
            item
            for item in response["beam_option_nodes"]
            if not _same_node(item, node)
        ]
        response["beam_options_classified"] = not response["beam_frontier_nodes"]
    return {"error": error, "branch_discarded": discarded}


def _contains_node(nodes, node):
    return any(_same_node(item, node) for item in nodes)


def _same_node(left, right):
    return bool(
        left
        and right
        and left.get("ontologyId") == right.get("ontologyId")
        and left.get("iri") == right.get("iri")
    )
