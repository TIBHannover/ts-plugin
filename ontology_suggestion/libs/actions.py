from django.core.exceptions import BadRequest
from django.conf import settings
import urllib
import requests
from .shape_test import test as test_onto_shape


def collectionSuggestionParams(
    collection_ids: str,
    username: str,
    email: str,
    ontoName: str,
    ontoPurl: str,
    reason: str,
):
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
    return {"title": title, "description": issue_content, "labels": label}


def ontologySuggestionParams(
    requestBody: any,
    collection_ids: str,
    username: str,
    email: str,
    ontoName: str,
    ontoPurl: str,
    reason: str,
):
    headers = {
        "PRIVATE-TOKEN": settings.GITLAB_TS_USER_API_TOKEN,
        "Content-Type": "application/json",
    }
    exist_url = (
        settings.GITLAB_API_BASE_URL
        + "{}/issues?labels=ontology_suggestion&state=opened&search={}&in=title".format(
            urllib.parse.quote(settings.ONTOLOGY_SUGGESTION_REPO, safe=""),
            ontoPurl,
        )
    )
    response = requests.get(exist_url, headers=headers)
    if response.status_code == 200:
        response = response.json()
        if len(response) > 0:
            raise BadRequest("suggestion exists.")

    issue_content = "from: {} ({})\n\n".format(username, email)
    issue_content += "Ontology Name: {}\n\nPURL: {}\n\nReason: {}\n\n".format(
        ontoName, ontoPurl, reason
    )
    issue_content += "Collection ID: <b>{}</b>\n\n".format(collection_ids)
    title = "Ontology Suggestion: {}".format(ontoPurl)
    label = "ontology_suggestion"
    for collection in collection_ids.split(","):
        label += ",{}".format(collection)

    validation = test_onto_shape(ontoPurl)
    if validation["shape_test_failed"]:
        issue_content += "\n<h4><b>Shape Test Failed</b></h4>\n\n"
        issue_content += "\n\n"
        issue_content += "Reason: {}\n\n".format(validation["error"][0]["text"])

    else:
        missing_fileds = {}
        if len(validation["error"]) > 0:
            for error in validation["error"]:
                # if not data.get(error['about']):
                #  abort(400, 'Please provide {}'.format(error['about']))
                missing_fileds[error["about"]] = requestBody.get(error["about"])
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

    return {
        "title": title,
        "description": issue_content,
        "labels": label,
    }, issue_content


def adopterSuggestionParams(
    requestBody,
    username,
    email,
    ontoName,
    ontoPurl,
):
    issue_content = "from: {} ({})\n\n".format(username, email)

    issue_content += "Ontology Name: {}\nPURL: {}\n\n".format(
        ontoName, ontoPurl
    )

    issue_content += "=== Adopter Information ===\n"
    issue_content += "Type: {}\n".format(requestBody.get("adopter_type"))
    issue_content += "Name: {}\n".format(requestBody.get("adopter_name"))
    issue_content += "Usage: {}\n".format(requestBody.get("usage_description"))
    issue_content += "Channel: {}\n".format(requestBody.get("usage_channel"))

    title = "Ontology Adopter: {}".format(ontoName)

    return {
        "title": title,
        "description": issue_content,
        "labels": "ontology_adopter",
    }