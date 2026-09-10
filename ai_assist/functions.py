import requests
from typing import Any
import urllib
from ai_assist.utils import convert_to_str, get_parent_from_term
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
        if size > 20:
            return "Error: size must be less than 20"
        params = {
            "search": query,
            "page": page,
            "size": size,
            "lang": "en",
            "exclusive": "true",
            "facetFields": "type ontologyId",
            "type": "class",
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
                }
            )
        return res
    except Exception as e:
        return f"Error: no results found: {e}"


def search_under_term(query: str, iri: str, page: int = 0, size: int = 20):
    try:
        if size > 20:
            return "Error: size has to be less than 20"
        resp = requests.get(
            f"{TS_BASE_URL_V1}search",
            params={
                "q": query,
                "exclusive": "false",
                "option": "LINEAR",
                "fieldList": "iri,label,short_form,obo_id,ontology_name",
                "queryFields": "iri,label,short_form,ontology_name",
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
        for r in resp[:5]:
            res.append(
                {
                    "label": r["label"],
                    "ontologyId": r["ontology_name"],
                    "iri": r["iri"],
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
        }
    except:
        return f"Error: no results found for {iri}"


def get_term_children(iri: str, ontologyId: str):
    try:
        iri = urllib.parse.quote(iri, safe="")
        resp = requests.get(
            f"{TS_BASE_URL}ontologies/{ontologyId}/classes/{urllib.parse.quote(iri, safe='')}/hierarchicalChildren?size=1000&lang=en&includeObsoleteEntities=false",
            timeout=REQUEST_TIMEOUT,
        )
        resp = resp.json()
        res = []
        for r in resp["elements"][:10]:
            definition = convert_to_str(r.get("definition", ""))
            res.append(
                {
                    "label": r["label"],
                    "definition": (
                        definition[:DEFNITION_MAX_LENGTH]
                        if isinstance(definition, str)
                        else ""
                    ),
                    "ontologyId": r["ontologyId"],
                    "synonym": r.get("synonym", []),
                }
            )
        return res
    except:
        return f"Error: no children found for {iri}"


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
            "description": "Search for terms. Results include a parent object whose label may be a string or list and whose IRI is a string.",
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
            "description": "Get term details, including a parent object whose label may be a string or list and whose IRI is a string.",
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
            "description": "get term children",
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
            "name": "search_under_term",
            "description": "Search within a term subtree. The page argument is the zero-based result offset.",
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
