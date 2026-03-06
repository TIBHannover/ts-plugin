from django.views.decorators.http import require_http_methods
from user_service.libs.decorators import (
    authentication_required,
    error_handler_decorator,
)
from user_service.libs.utils import create_json_response
from django.http import HttpResponseBadRequest
import requests
import json


@require_http_methods(["GET"])
def ping(request):
    return create_json_response({"response": "Pong"})


@error_handler_decorator
@authentication_required
@require_http_methods(["POST"])
def create_pub_link(request):
    data = json.loads(request.body)
    doi = data["doi"]
    ontology_id = data["ontology_id"]

    doi = doi.strip()
    doi_id = get_doi_id_from_url(doi)
    doi_source = get_doi_source(doi_id)

    return create_json_response({"response": doi_source})


def get_doi_source(doi_id):
    doi_source_resp = requests.get("https://doi.org/doiRA/{}".format(doi_id))
    if doi_source_resp.status_code != 200:
        return ""

    doi_source = doi_source_resp.json()
    if len(doi_source) == 0:
        return ""

    doi_source = doi_source[0].get("RA")
    if doi_source is None:
        return ""
    return doi_source


def get_doi_id_from_url(url):
    doi_id = ""
    if "https://dx.doi.org/" in url:
        doi_id = url.split("https://dx.doi.org/")[1]
    elif "https://doi.org/" in url:
        doi_id = url.split("https://doi.org/")[1]
    else:
        doi_id = url
    return doi_id

