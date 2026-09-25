from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from functools import partial
import logging
import requests
from typing import Any
import urllib
from ai_assist.utils import convert_to_str, get_parent_from_term, get_term_type
from ai_assist.models import Ontology

logger = logging.getLogger(__name__)

TS_BASE_URL = "https://api.terminology.tib.eu/api/v2/"
TS_BASE_URL_V1 = "https://api.terminology.tib.eu/api/"

DEFNITION_MAX_LENGTH = 300
REQUEST_TIMEOUT = (3.05, 10)
CHILD_SEARCH_PAGE_SIZE = 1000
CHILD_SEARCH_MAX_PAGES = 20


def search(
    query: str,
    ontologyId: str = "",
    excludedCandidates: list[dict[str, str]] | None = None,
    page = 0,
    size = 20
) -> list[dict[str, Any]] | str:
    try:
        if isinstance(page, bool) or not isinstance(page, int) or page < 0:
            return "Error: page must be a non-negative integer"
        if isinstance(size, bool) or not isinstance(size, int) or size < 1 or size > 20:
            return "Error: size must be an integer between 1 and 20"
        params = {
            "search": query,
            "page": page,
            "size": size,
            "lang": "en",
            "exclusive": "true",
            "facetFields": "type ontologyId",
        }
        if ontologyId:
            onto_details = get_ontology_detail(ontologyId)
            if "Error" in onto_details:
                raise Exception("Ontology not found")
            params["ontology"] = ontologyId.lower()
        resp = requests.get(
            f"{TS_BASE_URL}entities", params=params, timeout=REQUEST_TIMEOUT
        )
        resp = resp.json()
        resp = resp["elements"]
        res = []
        excluded = {
            (candidate["ontologyId"].casefold(), candidate["iri"])
            for candidate in excludedCandidates or []
        }
        for r in resp:
            if (r["ontologyId"].casefold(), r["iri"]) in excluded:
                continue
            definition = convert_to_str(r.get("definition", ""))
            res.append(
                {
                    "label": r["label"],
                    "iri": r["iri"],
                    "definition": (
                        definition[:DEFNITION_MAX_LENGTH]
                        if isinstance(definition, str)
                        else ""
                    ),
                    "ontologyId": r["ontologyId"],
                    "parent": get_parent_from_term(r),
                    "synonym": r.get("synonym", []),
                    "type": get_term_type(r)
                }
            )
        return res
    except Exception as e:
        return f"Error: no results found: {e}"


def batch_search(
    query: list[str],
    ontologyId: str = "",
    excludeCandidates: list[dict[str, str]] | None = None,
) -> dict[str, list[dict[str, Any]]] | str:
    if (
        not isinstance(query, list)
        or not 1 <= len(query) <= 5
        or not all(isinstance(value, str) for value in query)
        or len(set(query)) != len(query)
    ):
        return "Error: query must be a list of 1 to 5 unique strings"

    with ThreadPoolExecutor(max_workers=len(query)) as executor:
        results = executor.map(
            partial(
                search,
                ontologyId=ontologyId,
                excludedCandidates=excludeCandidates,
            ),
            query,
        )
    return {
        target: result if isinstance(result, list) else []
        for target, result in zip(query, results)
    }


def search_under_term(query: str, iri: str, page: int = 0, size: int = 20):
    try:
        if isinstance(page, bool) or not isinstance(page, int) or page < 0:
            return "Error: page must be a non-negative integer"
        if isinstance(size, bool) or not isinstance(size, int) or size < 1 or size > 20:
            return "Error: size must be an integer between 1 and 20"
        resp = requests.get(
            f"{TS_BASE_URL_V1}search",
            params={
                "q": query,
                "exclusive": "false",
                "option": "LINEAR",
                "exact": "false",
                "obsoletes": "false",
                "local": "false",
                "allChildrenOf": iri,
                "rows":size,
                "start": page,
                "format": "json",
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp = resp.json()
        resp = resp["response"]["docs"]
        if not resp:
            return f"Error: no results found for {iri}"
        res = []
        for r in resp:
            definition = convert_to_str(r.get("definition", ""))
            res.append(
                {
                    "label": r["label"],
                    "ontologyId": r["ontology_name"],
                    "iri": r["iri"],
                    "type": r["type"],
                    "definition": (
                            definition[:DEFNITION_MAX_LENGTH]
                            if isinstance(definition, str)
                            else ""
                        ),
                }
            )
        return res

    except Exception as e:
        return f"Error: no results found: {e}"


def get_term_detail(iri: str, ontologyId: str):
    original_iri = iri
    try:
        iri = urllib.parse.quote(iri, safe="")
        resp = requests.get(
            f"{TS_BASE_URL}ontologies/{ontologyId}/entities/{urllib.parse.quote(iri, safe='')}?lang=en",
            timeout=REQUEST_TIMEOUT,
        )
        resp = resp.json()
        definition = convert_to_str(resp.get("definition", ""))
        return {
            "label": convert_to_str(resp["label"]),
            "iri": resp["iri"],
            "definition": definition[:DEFNITION_MAX_LENGTH],
            "ontologyId": resp["ontologyId"],
            "parent": get_parent_from_term(resp),
            "synonym": resp.get("synonym", []),
            "type": get_term_type(resp)
        }
    except Exception:
        logger.exception("Unable to get term details for %s in %s", original_iri, ontologyId)
        return f"Error: no results found for {original_iri}"


def get_term_children(iri: str, ontologyId: str, term_type: str, page: int = 0):
    try:
        if term_type != "class" and term_type != "property":
            return "Errro: type of a term has to be either class or property."
        if isinstance(page, bool) or not isinstance(page, int) or page < 0:
            return "Error: page must be a non-negative integer"

        range_length  = 10
        iri = urllib.parse.quote(iri, safe="")
        base_url = f"{TS_BASE_URL}ontologies/{ontologyId}/classes/{urllib.parse.quote(iri, safe='')}/hierarchicalChildren?page={page}&size={range_length}&lang=en&includeObsoleteEntities=false"
        if term_type == "property":
            base_url = f"{TS_BASE_URL}ontologies/{ontologyId}/properties/{urllib.parse.quote(iri, safe='')}/hierarchicalChildren?page={page}&size={range_length}&lang=en&includeObsoleteEntities=false"

        resp = requests.get(base_url, timeout=REQUEST_TIMEOUT,)
        resp = resp.json()
        res = []
        for r in resp["elements"]:
            definition = convert_to_str(r.get("definition", ""))
            res.append(
                {
                    "label": r["label"],
                    "iri": r["iri"],
                    "definition": (
                        definition[:DEFNITION_MAX_LENGTH]
                        if isinstance(definition, str)
                        else ""
                    ),
                    "ontologyId": r["ontologyId"],
                    "synonym": r.get("synonym", []),
                    "type": get_term_type(r)
                }
            )
        return res
    except:
        return f"Error: no children found for {iri}"


def search_in_children(query: str, iri: str, ontologyId: str, term_type: str):
    try:
        if term_type not in ("class", "property"):
            return "Error: type of a term has to be either class or property."
        if not isinstance(query, str) or not query.strip():
            return "Error: query must be a non-empty string"

        entity_type = "classes" if term_type == "class" else "properties"
        encoded_iri = urllib.parse.quote(iri, safe="")
        url = (
            f"{TS_BASE_URL}ontologies/{ontologyId}/{entity_type}/{encoded_iri}/"
            "hierarchicalChildren"
        )
        normalized_query = query.casefold().strip()

        def score(child):
            synonyms = child.get("synonym", [])
            if isinstance(synonyms, str):
                synonyms = [synonyms]
            values = [convert_to_str(child.get("label", "")), *synonyms]
            scores = (
                (
                    1.0
                    if value.casefold().strip() == normalized_query
                    else SequenceMatcher(
                        None, normalized_query, value.casefold().strip()
                    ).ratio()
                )
                for value in values
                if isinstance(value, str) and value.strip()
            )
            return max(scores, default=0)

        match = None
        match_score = -1
        page = 0
        total_pages = 1
        while page < total_pages:
            response = requests.get(
                url,
                params={
                    "page": page,
                    "size": CHILD_SEARCH_PAGE_SIZE,
                    "lang": "en",
                    "includeObsoleteEntities": "false",
                },
                timeout=REQUEST_TIMEOUT,
            ).json()
            if page == 0:
                total_pages = response.get("page", {}).get("totalPages", 1)
                if (
                    isinstance(total_pages, bool)
                    or not isinstance(total_pages, int)
                    or total_pages < 1
                ):
                    return f"Error: invalid child pagination for {iri}"
                if total_pages > CHILD_SEARCH_MAX_PAGES:
                    return f"Error: too many children to search safely for {iri}"
            children = response.get("elements", [])
            if not isinstance(children, list) or len(children) > CHILD_SEARCH_PAGE_SIZE:
                return f"Error: invalid child page for {iri}"
            for child in children:
                child_score = score(child)
                if child_score > match_score:
                    match = child
                    match_score = child_score
            page += 1
        if match is None:
            return f"Error: no children found for {iri}"
        definition = convert_to_str(match.get("definition", ""))
        return {
            "label": convert_to_str(match["label"]),
            "iri": match["iri"],
            "definition": definition[:DEFNITION_MAX_LENGTH],
            "ontologyId": match["ontologyId"],
            "synonym": match.get("synonym", []),
            "type": get_term_type(match),
        }
    except Exception:
        logger.exception("Unable to search children for %s in %s", iri, ontologyId)
        return f"Error: no children found for {iri}"


def get_roots(ontologyId: str, type: str, page: int = 0):
    try:
        if type != "class" and type != "property":
            return "Error: type has to be either class or property."
        if isinstance(page, bool) or not isinstance(page, int) or page < 0:
            return "Error: page must be a non-negative integer"

        entity_type = "classes" if type == "class" else "properties"
        resp = requests.get(
            f"{TS_BASE_URL}ontologies/{ontologyId}/{entity_type}",
            params={
                "hasDirectParents": "false",
                "page": page,
                "size": 20,
                "lang": "en",
                "includeObsoleteEntities": "false",
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp = resp.json()
        res = []
        for r in resp["elements"]:
            definition = convert_to_str(r.get("definition", ""))
            res.append(
                {
                    "label": r["label"],
                    "iri": r["iri"],
                    "definition": (
                        definition[:DEFNITION_MAX_LENGTH]
                        if isinstance(definition, str)
                        else ""
                    ),
                    "ontologyId": r["ontologyId"],
                    "synonym": r.get("synonym", []),
                    "type": get_term_type(r),
                }
            )
        return res
    except:
        return f"Error: no roots found for {ontologyId}"


def get_individuals(ontologyId: str, page: int = 0):
    try:
        if isinstance(page, bool) or not isinstance(page, int) or page < 0:
            return "Error: page must be a non-negative integer"

        resp = requests.get(
            f"{TS_BASE_URL}ontologies/{ontologyId}/individuals",
            params={
                "lang": "en",
                "page": page,
                "size": 20,
                "includeObsoleteEntities": "false",
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp = resp.json()
        res = []
        for r in resp["elements"]:
            definition = convert_to_str(r.get("definition", ""))
            res.append(
                {
                    "label": r["label"],
                    "iri": r["iri"],
                    "definition": (
                        definition[:DEFNITION_MAX_LENGTH]
                        if isinstance(definition, str)
                        else ""
                    ),
                    "ontologyId": r["ontologyId"],
                    "synonym": r.get("synonym", []),
                    "type": get_term_type(r),
                }
            )
        return res
    except:
        return f"Error: no individuals found for {ontologyId}"


def get_ontology_detail(ontologyId: str):
    try:
        onto = Ontology.objects.filter(ontologyId=ontologyId).first()
        if not onto:
           return f"Error: no ontology found for {ontologyId}"
        return onto.to_dict()
    except:
        return f"Error: no ontology found for {ontologyId}"


def ontologies_list(
    collection: str = "", subject: str = "", hosted_on_github: bool = True
):
    ontologies = Ontology.objects.all()
    if hosted_on_github:
        ontologies = ontologies.filter(
            repo_url__iregex=r"^https?://(?:www\.)?github\.com(?:/|$)"
        )
    if collection:
        ontologies = ontologies.filter(collection__contains=[collection])
    if subject:
        ontologies = ontologies.filter(subjects__contains=[subject])
    return [ontology.to_dict() for ontology in ontologies]


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "batch_search",
            "description": "Search for up to five queries in parallel. Results are keyed by query and include label, IRI, definition, ontology ID, parent, synonyms, and term type (class, property, or individual). The parent label may be a string or list and its IRI is a string.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "maxItems": 5,
                        "uniqueItems": True,
                    },
                    "ontologyId": {"type": "string"},
                    "excludeCandidates": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "ontologyId": {"type": "string"},
                                "iri": {"type": "string"},
                            },
                            "required": ["ontologyId", "iri"],
                        },
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_ontology_detail",
            "description": "Get cached ontology metadata: ontologyId, repo_url, definition, subjects, collection, importsFrom, exportsTo, label, and lang. The loaded timestamp is not returned.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ontologyId": {"type": "string"},
                },
                "required": ["ontologyId"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_term_detail",
            "description": "Get term details, including label, IRI, definition, ontology ID, parent, synonyms, and term type (class, property, or individual). The parent label may be a string or list and its IRI is a string.",
            "parameters": {
                "type": "object",
                "properties": {
                    "iri": {"type": "string"},
                    "ontologyId": {"type": "string"},
                },
                "required": ["iri", "ontologyId"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_in_children",
            "description": "Search all direct children of a class or property locally and return the closest matching child. The upstream API does not support child search. The result includes label, IRI, definition, ontology ID, synonyms, and term type.",
            "parameters": {
                "type": "object",
                "properties": {
                    "iri": {"type": "string"},
                    "ontologyId": {"type": "string"},
                    "query": {"type": "string"},
                    "term_type": {
                        "type": "string",
                        "enum": ["class", "property"],
                        "description": "Type of the parent term, as returned by another term tool.",
                    },
                },
                "required": ["query", "iri", "ontologyId", "term_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ontologies_list",
            "description": "List all cached ontologies hosted on GitHub. Results include ontologyId, repo_url, definition, subjects, collection, importsFrom, exportsTo, label, and lang. Choose the closest ontology using the term label and definition as primary criteria. Domain is only a low-weight hint and never a required metadata match.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hosted_on_github": {
                        "type": "boolean",
                        "default": True,
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_roots",
            "description": "Get one page of root classes or properties for an ontology. Each page contains at most 20 roots, so increment page when more results may be needed. Results include label, IRI, definition, ontology ID, synonyms, and term type.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ontologyId": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": ["class", "property"],
                        "description": "Type of root terms to retrieve.",
                    },
                    "page": {
                        "type": "integer",
                        "description": "Zero-based page number. Page size is fixed at 20 results.",
                        "minimum": 0,
                        "default": 0,
                    },
                },
                "required": ["ontologyId", "type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_individuals",
            "description": "Get one page of individuals for an ontology. Each page contains at most 20 individuals, so increment page when more results may be needed. Results include label, IRI, definition, ontology ID, synonyms, and the individual term type.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ontologyId": {"type": "string"},
                    "page": {
                        "type": "integer",
                        "description": "Zero-based page number. Page size is fixed at 20 results.",
                        "minimum": 0,
                        "default": 0,
                    },
                },
                "required": ["ontologyId"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_under_term",
            "description": "Search within a term subtree. Results include label, ontology ID, IRI, term type, and definition. The page argument is the zero-based result offset.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "iri": {"type": "string"},
                    "page": {
                        "type": "integer",
                        "description": "Zero-based result offset.",
                        "minimum": 0,
                        "default": 0,
                    },
                    "size": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 20,
                        "default": 20,
                    },
                },
                "required": ["query", "iri"],
            },
        },
    },
]
