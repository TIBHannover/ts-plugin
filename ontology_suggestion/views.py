from user_service.libs.utils import create_json_response
from user_service.libs.decorators import (
    error_handler_decorator,
    authentication_required,
)
import requests
import urllib.parse
from .libs.shape_test import test as test_onto_shap
from django.views.decorators.http import require_http_methods
import json
from django.conf import settings
from django.core.exceptions import BadRequest
from user_service.middlewares.request import get_client_id_from_request
from django.http import HttpResponseServerError
from .libs.actions import collectionSuggestionParams, ontologySuggestionParams


@require_http_methods(["GET"])
def ping(request):
    return create_json_response({"response": "Pong"})


@error_handler_decorator
@authentication_required
@require_http_methods(["POST"])
def create(request):
    data = json.loads(request.body)
    email = data["email"]
    username = data["username"]
    reason = data["reason"]
    ontoName = data["name"]
    ontoPurl = data["purl"]
    collection_ids = data.get("collection_ids", "")
    collection_suggestion = data.get("collection_suggestion", False)

    headers = {
        "PRIVATE-TOKEN": settings.GITLAB_TS_USER_API_TOKEN,
        "Content-Type": "application/json",
    }

    parameters = {}
    issue_content = ""
    if collection_suggestion:
        parameters = collectionSuggestionParams(
            collection_ids=collection_ids,
            username=username,
            email=email,
            ontoName=ontoName,
            ontoPurl=ontoPurl,
            reason=reason,
        )
    else:
        # ontology suggestion
        parameters, issue_content = ontologySuggestionParams(
            requestBody=data,
            collection_ids=collection_ids,
            username=username,
            email=email,
            ontoName=ontoName,
            ontoPurl=ontoPurl,
            reason=reason,
        )

    if (
        get_client_id_from_request() == "nfdi4chem"
        or "nfdi4chem" in collection_ids.lower()
    ):
        adminIds = settings.NFDI4CHEM_GITLAB_ADMIN_IDS
        if adminIds:
            for id in adminIds.split(","):
                issue_content = "@{}\n\n".format(id) + issue_content
            parameters["description"] = issue_content

    parameters["confidential"] = True
    url = settings.GITLAB_API_BASE_URL + "{}/issues".format(
        urllib.parse.quote(settings.ONTOLOGY_SUGGESTION_REPO, safe="")
    )
    response = requests.post(url, json=parameters, headers=headers)
    if response.status_code != 201:
        return HttpResponseServerError("Failed. Please try again later.")

    return create_json_response({"response": "ontology is suggested successfully"})


@error_handler_decorator
@authentication_required
@require_http_methods(["GET"])
def testshape(request):
    args = request.GET
    ontoPurl = args.get("purl")
    validation = test_onto_shap(ontoPurl)
    if not validation:
        raise BadRequest("Validation process aborted")
    return create_json_response({"response": validation})


@error_handler_decorator
@authentication_required
@require_http_methods(["GET"])
def suggestion_exist(request):
    data = request.GET
    purl = data["purl"]
    headers = {
        "PRIVATE-TOKEN": settings.GITLAB_TS_USER_API_TOKEN,
        "Content-Type": "application/json",
    }
    url = (
        settings.GITLAB_API_BASE_URL
        + "{}/issues?labels=ontology_suggestion&state=opened&search={}&in=title".format(
            urllib.parse.quote(settings.ONTOLOGY_SUGGESTION_REPO, safe=""),
            purl,
        )
    )
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        response = response.json()
        if not response:
            return create_json_response({"exist": False})
        return create_json_response({"exist": True})
    return HttpResponseServerError("something went wrong")
