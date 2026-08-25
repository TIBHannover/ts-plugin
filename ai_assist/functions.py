import requests
from typing import Any
import urllib

TS_BASE_URL = "https://api.terminology.tib.eu/api/v2/"
TS_BASE_URL_V1 = "https://api.terminology.tib.eu/api/"

DEFNITION_MAX_LENGTH = 100


def search(query: str, ontologyId: str = "") -> list[dict[str, Any]]:
    try:
        url = f"{TS_BASE_URL}entities?search={query}&page=0&size=20&lang=en&exclusive=true&facetFields=type+ontologyId&type=class"
        if ontologyId:
            onto_details = get_ontology_detail(ontologyId)
            if "Error" in onto_details:
                raise Exception("Ontology not found")
            url += f"&ontology={ontologyId.lower()}"
        resp = requests.get(url)
        resp = resp.json()
        resp = resp["elements"]
        res = []
        for r in resp:
            res.append(
                {
                    "label": r["label"],
                    "iri": r["iri"],
                    "definition": r.get("definition", "")[:DEFNITION_MAX_LENGTH],
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
        iri = urllib.parse.quote(iri, safe="")
        resp = requests.get(
            f"{TS_BASE_URL_V1}search?q={query}&exclusive=false&option=LINEAR&fieldList=iri%2Clabel%2Cshort_form%2Cobo_id%2Contology_name&queryFields=iri%2Clabel%2Cshort_form%2Contology_name&exact=false&obsoletes=false&local=false&allChildrenOf={iri}&rows=20&start=0&format=json"
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
            f"{TS_BASE_URL}ontologies/{ontologyId}/entities/{urllib.parse.quote(iri, safe='')}?lang=en"
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
            f"{TS_BASE_URL}ontologies/{ontologyId}/classes/{urllib.parse.quote(iri, safe='')}/hierarchicalChildren?size=1000&lang=en&includeObsoleteEntities=false"
        )
        resp = resp.json()
        res = []
        for r in resp["elements"][:10]:
            res.append(
                {
                    "label": r["label"],
                    "definition": r.get("definition", "")[:DEFNITION_MAX_LENGTH],
                    "ontologyId": r["ontologyId"],
                    "synonym": r.get("synonym", []),
                }
            )
        return res
    except:
        return f"Error: no children found for {iri}"


def get_ontology_detail(ontologyId: str):
    try:
        resp = requests.get(f"{TS_BASE_URL}ontologies/{ontologyId}?lang=en")
        resp = resp.json()
        return {
            "label": resp["label"],
            "definition": resp.get("definition", "")[:DEFNITION_MAX_LENGTH],
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
