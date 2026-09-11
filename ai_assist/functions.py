import requests
from typing import Any
import urllib
from ai_assist.utils import convert_to_str, get_parent_from_term, get_term_type
from ai_assist.models import Ontology

TS_BASE_URL = "https://api.terminology.tib.eu/api/v2/"
TS_BASE_URL_V1 = "https://api.terminology.tib.eu/api/"

DEFNITION_MAX_LENGTH = 300
REQUEST_TIMEOUT = (3.05, 10)


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
    try:
        iri = urllib.parse.quote(iri, safe="")
        resp = requests.get(
            f"{TS_BASE_URL}ontologies/{ontologyId}/entities/{urllib.parse.quote(iri, safe='')}?lang=en",
            timeout=REQUEST_TIMEOUT,
        )
        resp = resp.json()
        definition = convert_to_str(resp.get("definition", ""))
        return {
            "label": resp["label"],
            "definition": definition[:DEFNITION_MAX_LENGTH],
            "ontologyId": resp["ontologyId"],
            "parent": get_parent_from_term(resp),
            "synonym": resp.get("synonym", []),
            "type": get_term_type(resp)
        }
    except:
        return f"Error: no results found for {iri}"


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


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Search for terms. Results include label, IRI, definition, ontology ID, parent, synonyms, and term type (class, property, or individual). The parent label may be a string or list and its IRI is a string.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "ontologyId": {"type": "string"},
                    "page": {
                        "type": "integer",
                        "description": "Zero-based result-page number.",
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
            "description": "Get term details, including label, definition, ontology ID, parent, synonyms, and term type (class, property, or individual). The parent label may be a string or list and its IRI is a string.",
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
            "name": "get_term_children",
            "description": "Get one page of direct child terms for a class or property. Each page contains at most 10 children, so increment page when more results may be needed. Results include label, IRI, definition, ontology ID, synonyms, and term type.",
            "parameters": {
                "type": "object",
                "properties": {
                    "iri": {"type": "string"},
                    "ontologyId": {"type": "string"},
                    "term_type": {
                        "type": "string",
                        "enum": ["class", "property"],
                        "description": "Type of the parent term, as returned by another term tool.",
                    },
                    "page": {
                        "type": "integer",
                        "description": "Zero-based page number. Page size is fixed at 10 results.",
                        "minimum": 0,
                        "default": 0,
                    },
                },
                "required": ["iri", "ontologyId", "term_type"],
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
