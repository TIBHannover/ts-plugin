from django.http import JsonResponse
from django.conf import settings
import requests


def create_json_response(response_dict):
    return JsonResponse({"_result": response_dict})


def fetch_ontology_collections(ontologyId:str) -> list:
    try:                       
        url = settings.OLS_API_BASE_URL + ontologyId
        ontology = requests.get(url)            
        if ontology.status_code != 200:
            return []
        ontology = ontology.json()            
        return ontology['config']['classifications'][0]['collection']

    except:
        return []
