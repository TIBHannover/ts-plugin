import requests
from typing import Any
import urllib

TS_BASE_URL = "https://api.terminology.tib.eu/api/v2/"
TS_BASE_URL_V1 = "https://api.terminology.tib.eu/api/"

DEFNITION_MAX_LENGTH = 100
REQUEST_TIMEOUT = (3.05, 10)


def search(
    query: str,
    ontologyId: str = "",
    excludedCandidates: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    try:
        params = {
            "search": query,
            "page": 0,
            "size": 20,
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
            definition = r.get("definition", "")
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
                    "parent_iri": r.get("directParent", ""),
                    "synonym": r.get("synonym", []),
                }
            )
        return res
    except Exception as e:
        return f"Error: no results found: {e}"


def search_under_term(query: str, iri: str):
    try:
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
                "rows": 20,
                "start": 0,
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
        return {
            "label": resp["label"],
            "definition": resp.get("definition", ""),
            "ontologyId": resp["ontologyId"],
            "parent_iri": resp.get("directParent", ""),
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
            definition = r.get("definition", "")
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
        resp = requests.get(
            f"{TS_BASE_URL}ontologies/{ontologyId}?lang=en",
            timeout=REQUEST_TIMEOUT,
        )
        resp = resp.json()
        definition = resp.get("definition", "")
        return {
            "label": resp["label"],
            "definition": (
                definition[:DEFNITION_MAX_LENGTH]
                if isinstance(definition, str)
                else ""
            ),
        }
    except:
        return f"Error: no ontology found for {ontologyId}"


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "search in a terminology database for a given query",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "ontologyId": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_ontology_detail",
            "description": "get ontology detail",
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
            "description": "get term detail",
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
            "description": "search under a term in a tree structure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "iri": {"type": "string"},
                },
                "required": ["query", "iri"],
            },
        },
    },
]
