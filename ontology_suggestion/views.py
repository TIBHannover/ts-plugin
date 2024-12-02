
from user_service.libs.utils import create_json_response
from user_service.libs.decorators import error_handler_decorator, authentication_required
import requests
import urllib.parse
from .libs.shape_test import testShape 
from django.views.decorators.http import require_http_methods
import json
from django.conf import settings
from django.core.exceptions import BadRequest 
from user_service.middlewares.request import get_client_id_from_request
from django.http import HttpResponseServerError




@require_http_methods(['GET'])
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

    if collection_suggestion and collection_suggestion == "true":
        if collection_ids == "":
            raise BadRequest("Collection Ids are missing")
        issue_content = "from: {} ({})\n\n".format(username, email)
        issue_content += "Ontology Name: {}\n\nPURL: {}\n\nReason: {}\n\n".format(
            ontoName, ontoPurl, reason
        )
        issue_content += "Target Collection IDs: \n\n"
        label = "add_to_collection"
        for colId in collection_ids.split(","):
            issue_content += "{}\n\n".format(colId)
            label += ",{}".format(colId)

        title = "Add to Collection: {}".format(ontoName)
        parameters = {"title": title, "description": issue_content, "labels": label}

    else:
        # ontology suggestion

        exist_url = (
            settings.GITLAB_API_BASE_URL
            + "{}/issues?labels=ontology_suggestion&state=opened&search={}&in=title".format(
                urllib.parse.quote(
                    settings.ONTOLOGY_SUGGESTION_REPO, safe=""
                ),
                ontoPurl,
            )
        )
        response = requests.get(exist_url, headers=headers)
        if response.status_code == 200:
            response = response.json()
            if len(response) > 0:
                raise BadRequest("suggestion exists.")

        validation = testShape(ontoPurl)
        if not validation:
            raise BadRequest("Validation process aborted")

        missing_fileds = {}
        if len(validation["error"]) > 0:
            for error in validation["error"]:
                # if not data.get(error['about']):
                #  abort(400, 'Please provide {}'.format(error['about']))
                missing_fileds[error["about"]] = data.get(error["about"])

        issue_content = "from: {} ({})\n\n".format(username, email)
        issue_content += "Ontology Name: {}\n\nPURL: {}\n\nReason: {}\n\n".format(
            ontoName, ontoPurl, reason
        )
        issue_content += "Collection ID: <b>{}</b>\n\n".format(collection_ids)
        issue_content += "<h4><b>Missing Fields</b></h4> These fields are missing from the ontology based on the SHACL test, and instead, user was asked to provide them.\n\n"
        issue_content += "\n\n"
        for key, val in missing_fileds.items():
            issue_content += "{}: {}\n\n".format(key, val)

        issue_content += "\n<h4><b>Full list of validation errors</b></h4>\n\n"
        for err in validation["error"]:
            issue_content += "{}\n\n".format(err["text"])

        issue_content += "\n<h4><b>Validation Warnings</b></h4> These warnings are also found during the SHACL test.\n\n"
        for info in validation["info"]:
            issue_content += "{}\n\n".format(info)

        title = "Ontology Suggestion: {}".format(ontoPurl)
        label = "ontology_suggestion"
        for collection in collection_ids.split(","):
            label += ",{}".format(collection)

        parameters = {"title": title, "description": issue_content, "labels": label}

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
@require_http_methods(['GET'])
def testshape(request):
    data = request.GET
    ontoPurl = data["purl"]
    validation = testShape(ontoPurl)
    if not validation:
        raise BadRequest("Validation process aborted")
    return create_json_response({"response": validation})


@error_handler_decorator
@authentication_required
@require_http_methods(['GET'])
def suggestion_exist(request):
    data = request.GET
    purl = data["purl"]
    headers = {
        "PRIVATE-TOKEN": settings.GITLAB_TS_USER_API_TOKEN,
        "Content-Type": "application/json",
    }
    url = settings.GITLAB_API_BASE_URL + "{}/issues?labels=ontology_suggestion&state=opened&search={}&in=title".format(
        urllib.parse.quote(settings.ONTOLOGY_SUGGESTION_REPO, safe=""),
        purl,
    )
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        response = response.json()
        if not response:
            return create_json_response({"exist": False})
        return create_json_response({"exist": True})
    return HttpResponseServerError("something went wrong")
