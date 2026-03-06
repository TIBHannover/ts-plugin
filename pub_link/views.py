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

    doi_id = ""
    doi = doi.strip()
    if "https://dx.doi.org/" in doi:
        doi_id = doi.split("https://dx.doi.org/")[1]
    elif "https://doi.org/" in doi:
        doi_id = doi.split("https://doi.org/")[1]
    else:
        doi_id = doi

    doi_source_resp = requests.get("https://doi.org/doiRA/{}".format(doi_id))
    if doi_source_resp.status_code != 200:
        return HttpResponseBadRequest("Invalid doi")

    doi_source = doi_source_resp.json()
    if len(doi_source) == 0:
        return HttpResponseBadRequest("Invalid doi")

    doi_source = doi_source[0].get("RA")
    if doi_source is None:
        return HttpResponseBadRequest("Invalid doi")

    return create_json_response({"response": doi_source})
