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

def select_beam_subtrees(options):
    return options


TERM_REQUEST_SEARCH_TOOLS = SHARED_TOOLS + [
    {
        "type": "function",
        "function": {
            "name": "select_beam_subtrees",
            "description": (
                "Select up to three current beam options, ordered from best to least "
                "suitable, and classify each as active or terminal. Unselected options "
                "are discarded. Previously selected terminal parents persist, so fill "
                "only the remaining slots. For each option, explicitly judge whether "
                "it is semantically a type or subtype of the requested category."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "options": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "iri": {"type": "string"},
                                "status": {
                                    "type": "string",
                                    "enum": ["active", "terminal"],
                                },
                                "category_compatible": {
                                    "type": "boolean",
                                    "description": "Whether this term is semantically a type or subtype of the requested category.",
                                },
                            },
                            "required": ["iri", "status", "category_compatible"],
                        },
                        "minItems": 1,
                        "maxItems": 3,
                    }
                },
                "required": ["options"],
            },
        },
    },
]
TERM_REQUEST_SEARCH_FUNCTIONS = {
    "batch_search": batch_search,
    "get_term_detail": get_term_detail,
    "search_in_children": search_in_children,
    "get_roots": get_roots,
    "get_individuals": get_individuals,
    "get_ontology_detail": get_ontology_detail,
    "ontologies_list": ontologies_list,
    "search_under_term": search_under_term,
    "select_beam_subtrees": select_beam_subtrees,
}
