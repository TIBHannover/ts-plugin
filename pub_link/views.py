from django.views.decorators.http import require_http_methods
from user_service.libs.decorators import (
    authentication_required,
    error_handler_decorator,
)
from user_service.libs.utils import create_json_response
from django.http import HttpResponseBadRequest
import requests
import json
from pub_link.models import PubLinkModel
from datetime import datetime as _time
from user.models import UserModel
from user_service.middlewares.request import get_username_from_request
from django.http import Http404
from django.core.exceptions import PermissionDenied

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
    ontology_id = ontology_id.strip()
    ontology_id = ontology_id.lower()
    username = get_username_from_request()
    user = UserModel.get_by_username(username=username)

    doi = doi.strip()
    doi_id = get_doi_id_from_url(doi)
    doi_source = get_doi_source(doi_id)
    if not doi_source:
        return create_json_response({"error": "Invalid DOI"})

    if doi_source == "DataCite":
        citation = get_citation_from_datacite(doi_id)
    else:
        citation = get_citation_from_crossref(doi_id)

    if not citation:
        raise Exception("Issue in getting citation")

    record = PubLinkModel()
    record.ontology_id = ontology_id
    record.doi = doi
    record.citation = citation
    record.created_at = _time.now()
    record.creator = user
    record.save()
    if not record.id:
        return HttpResponseBadRequest("Something went wrong.")

    return create_json_response({"created": record.to_dict()})


@error_handler_decorator
@require_http_methods(["GET"])
def get_pub_link(request, ontology_id):
    ontology_id = ontology_id.strip()
    ontology_id = ontology_id.lower()
    pub_links = PubLinkModel.objects.filter(ontology_id=ontology_id).all()
    return create_json_response(
        {"publications": [pub_link.to_dict() for pub_link in pub_links]}
    )


@error_handler_decorator
@authentication_required
@require_http_methods(["DELETE"])
def delete_pub_link(request, id):
    pub_link = PubLinkModel.objects.filter(id=id).first()
    if not pub_link:
        raise Http404("Publication link does not exist.")
    username = get_username_from_request()
    user = UserModel.get_by_username(username=username)
    if pub_link.creator.id != user.id:
        raise PermissionDenied("Not authorized")
    pub_link.delete()
    return create_json_response({"deleted": True})


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


def get_citation_from_crossref(doi_id):
    url = "https://api.crossref.org/works/{}".format(doi_id)
    publicaton_resp = requests.get(url)
    if publicaton_resp.status_code != 200:
        return ""

    publicaton_resp = publicaton_resp.json()
    pub_data = publicaton_resp.get("message", {})
    if not pub_data:
        return ""

    citation = ""
    for au in pub_data.get("author", []):
        name = au.get("given", "")
        family = au.get("family", "")
        citation += "{} {}. ".format(name, family)

    if len(pub_data.get("title", [])) > 0:
        citation += '"{}". '.format(pub_data["title"][0])

    citation += "({}). ".format(pub_data["created"]["date-parts"][0][0])
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
