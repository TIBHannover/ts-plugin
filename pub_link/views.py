from django.views.decorators.http import require_http_methods
from user_service.libs.decorators import (
    authentication_required,
    error_handler_decorator,
)
from user_service.libs.utils import create_json_response
from django.http import HttpResponseBadRequest
import requests
import json

DOI_VALID_SOURCES = ["Crossref", "DataCite"]


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
    if not doi_source:
        return HttpResponseBadRequest("Invalid DOI")

    if doi_source == "DataCite":
        citation = get_citation_from_datacite(doi_id)
    else:
        citation = ""

    return create_json_response({"response": citation})


def get_citation_from_datacite(doi_id):
    url = "https://api.datacite.org/dois/{}".format(doi_id)
    publicaton_resp = requests.get(url)
    if publicaton_resp.status_code != 200:
        return ""

    publicaton = publicaton_resp.json()
    if publicaton.get("data") is None:
        return ""
    pub_data = publicaton["data"]["attributes"]

    citation = ""
    authors = pub_data.get("creators", [])
    for au in authors:
        name = au.get("name")
        au_parts = name.split(",")
        if len(au_parts) > 1:
            citation += "{} {}. ".format(au_parts[1], au_parts[0])
        else:
            citation += "{}. ".format(au_parts[0])

    if len(pub_data.get("titles", [])) > 0:
        citation += '"{}." '.format(pub_data["titles"][0]["title"])

    citation += "({}). ".format(pub_data["publicationYear"])
    return citation


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
    if doi_source not in DOI_VALID_SOURCES:
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

