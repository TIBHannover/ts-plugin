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

TERM_REQUEST_SEARCH_TOOLS = SHARED_TOOLS
TERM_REQUEST_SEARCH_FUNCTIONS = {
    "batch_search": batch_search,
    "get_term_detail": get_term_detail,
    "search_in_children": search_in_children,
    "get_roots": get_roots,
    "get_individuals": get_individuals,
    "get_ontology_detail": get_ontology_detail,
    "ontologies_list": ontologies_list,
    "search_under_term": search_under_term,
}
