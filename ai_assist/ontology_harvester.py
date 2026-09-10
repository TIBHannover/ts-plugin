import logging

import requests
from django.utils import timezone

from ai_assist.models import Ontology
from ai_assist.utils import convert_to_str

ONTOLOGIES_URL = "https://api.terminology.tib.eu/api/v2/ontologies?size=1000"
logger = logging.getLogger(__name__)


def harvest_ontologies():
    response = requests.get(ONTOLOGIES_URL, timeout=30)
    response.raise_for_status()
    ontologies = response.json().get("elements", [])
    for onto in ontologies:
        try:
            ontology_id = onto["ontologyId"]
            defaults = {
                "label": onto.get("title", ""),
                "repo_url": onto.get("repo_url", ""),
                "definition": convert_to_str(onto.get("definition", "")),
                "subjects": get_subjects(onto),
                "collection": get_collections(onto),
                "importsFrom": to_string_list(onto.get("importsFrom", [])),
                "exportsTo": to_string_list(onto.get("exportsTo", [])),
                "lang": to_string_list(onto.get("language", [])),
                "loaded": timezone.now(),
            }
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Skipping invalid ontology: %s", exc)
            continue
        Ontology.objects.update_or_create(ontologyId=ontology_id, defaults=defaults)



def to_string_list(value):
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def get_subjects(onto):
    classifications = onto.get("classifications", [])
    if len(classifications) < 2:
        return []
    return to_string_list(classifications[1].get("subject", []))


def get_collections(onto):
    classifications = onto.get("classifications", [])
    if not classifications:
        return []
    return to_string_list(classifications[0].get("collection", []))
