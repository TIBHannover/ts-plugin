from ai_assist.functions import (
    TOOLS as SHARED_TOOLS,
    batch_search,
    get_individuals,
    get_ontology_detail,
    get_roots,
    get_term_detail,
    ontologies_list,
    search_under_term,
    search_in_children,
)


def add_parent_candidate(iri, category_compatible):
    return {"iri": iri, "category_compatible": category_compatible}


TERM_REQUEST_SEARCH_TOOLS = SHARED_TOOLS + [
    {
        "type": "function",
        "function": {
            "name": "add_parent_candidate",
            "description": (
                "Add a returned ontology term to the parent-candidate list. A candidate "
                "can be at any ontology depth and does not need to be a leaf."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "iri": {"type": "string"},
                    "category_compatible": {
                        "type": "boolean",
                        "description": (
                            "Whether the term is semantically a type or subtype of the "
                            "requested category. Must be true for a parent candidate."
                        ),
                    },
                },
                "required": ["iri", "category_compatible"],
            },
        },
    }
]
TERM_REQUEST_SEARCH_FUNCTIONS = {
    "add_parent_candidate": add_parent_candidate,
    "batch_search": batch_search,
    "get_term_detail": get_term_detail,
    "search_in_children": search_in_children,
    "get_roots": get_roots,
    "get_individuals": get_individuals,
    "get_ontology_detail": get_ontology_detail,
    "ontologies_list": ontologies_list,
    "search_under_term": search_under_term,
}
