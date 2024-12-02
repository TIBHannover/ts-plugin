from django.http import JsonResponse
from django.conf import settings
import requests
from user_service.middlewares.request import get_client_id_from_request
from typing import Any, Optional


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


def get_frontend_base_url() -> str:
    if get_client_id_from_request() == "general":
        return settings.TIB_GENERAL_FRONTEND_ADDRESS

    if get_client_id_from_request() == "nfdi4chem":
        return settings.NFDI4CHEM_FRONTEND_ADDRESS
    
    return settings.NFDI4ING_FRONTEND_ADDRESS



def add_to_dict_if_value_is_not_none(target_dict:dict, key:str, value:Any):
    if value:
        target_dict[key] = value


def get_int_from_string(string:str) -> Optional[int]:
    try:
        number = int(string)
        return number
    except:
        return None
