from concurrent.futures import ThreadPoolExecutor

from ai_assist.functions import (
    TOOLS as SHARED_TOOLS,
    batch_search,
    get_individuals,
    get_ontology_detail,
    get_roots,
    get_term_detail,
    ontologies_list,
    search,
    search_under_term,
    search_in_children,
)
from .state import get_category_values

CATEGORY_SEARCH_MAX_PAGES = 20
CATEGORY_SEARCH_PAGE_SIZE = 20


def find_category_terms(ontologyId, category):
    queries = get_category_values(category)
    category_values = {query.casefold() for query in queries}
    results = {query: [] for query in queries}
    if not queries:
        return results
    ontology = get_ontology_detail(ontologyId)
    if not isinstance(ontology, dict):
        return results
    seen = set()
    jobs = [
        (query, page)
        for index, query in enumerate(queries)
        for page in range(
            CATEGORY_SEARCH_MAX_PAGES // len(queries)
            + (index < CATEGORY_SEARCH_MAX_PAGES % len(queries))
        )
    ]

    def run_search(job):
        query, page = job
        return query, search(
            query,
            ontologyId,
            page=page,
            size=CATEGORY_SEARCH_PAGE_SIZE,
            validate_ontology=False,
        )

    with ThreadPoolExecutor(max_workers=min(5, len(jobs))) as executor:
        pages = executor.map(run_search, jobs)
    for query, terms in pages:
        if not isinstance(terms, list):
            continue
        for term in terms:
            synonyms = term.get("synonym", [])
            if isinstance(synonyms, str):
                synonyms = [synonyms]
            values = _text_values(term.get("label", "")) + _text_values(synonyms)
            term_id = (term.get("ontologyId"), term.get("iri"))
            if (
                term.get("type") in ("class", "property")
                and term_id not in seen
                and any(
                    isinstance(value, str)
                    and value.strip().casefold() in category_values
                    for value in values
                )
            ):
                results[query].append(term)
                seen.add(term_id)
    return results


def _text_values(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


TERM_REQUEST_SEARCH_TOOLS = SHARED_TOOLS + [
    {
        "type": "function",
        "function": {
            "name": "find_category_terms",
            "description": (
                "Search paginated results in the selected ontology for exact label or "
                "synonym matches to the requested category. Use a returned class or "
                "property as the anchor for structural parent traversal."
            ),
            "parameters": {
                "type": "object",
                "properties": {"ontologyId": {"type": "string"}},
                "required": ["ontologyId"],
            },
        },
    }
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
    "find_category_terms": find_category_terms,
}
