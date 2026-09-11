from ai_assist.functions import (
    TOOLS as SHARED_TOOLS,
    get_individuals,
    get_ontology_detail,
    get_roots,
    get_term_children,
    get_term_detail,
    search,
    search_under_term,
)

TERM_REQUEST_SEARCH_TOOLS = SHARED_TOOLS
TERM_REQUEST_SEARCH_FUNCTIONS = {
    "search": search,
    "get_term_detail": get_term_detail,
    "get_term_children": get_term_children,
    "get_roots": get_roots,
    "get_individuals": get_individuals,
    "get_ontology_detail": get_ontology_detail,
    "search_under_term": search_under_term,
}
