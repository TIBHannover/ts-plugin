from user_service.libs.decorators import error_handler_decorator
import requests
import urllib.parse
from user_service.middlewares.request import get_client_id_from_request
from django.views.decorators.http import require_http_methods
from user_service.libs.utils import create_json_response
from django.http import HttpResponseBadRequest, HttpResponseServerError
from django.conf import settings
import json


APP_ERROR_TITLE_PREFIX = "Application Error on: "


@require_http_methods(["GET"])
def ping(request):
    return create_json_response({"response": "Pong"})


@error_handler_decorator
@require_http_methods(["POST"])
def create(request):
    data = json.loads(request.body)
    issueTypes = {"1": "Question", "2": "Problem"}

    title = data["title"]
    description = data["description"]
    email = data["email"]
    name = data["name"]
    request_type = data["type"]
    safeQuestion = data["safeQuestion"]
    safeAnswer = data["safeAnswer"]
    appError = data["appError"]

    safeNumbers = safeQuestion.split("+")
    if len(safeNumbers) != 2 or int(safeNumbers[0]) + int(safeNumbers[1]) != int(
        safeAnswer
    ):
        return HttpResponseBadRequest("Invalid safe question and answer.")

    issue_content = "from: {} ({})\n\n{}".format(name, email, description)
    if appError:
        issue_content = "from: Application Error: \n\n{}".format(description)
        title = APP_ERROR_TITLE_PREFIX + title
        request_type = "2"
        if appErrorExist(title):
            # error has been reported before. So no need to create it again but we inform the client that everything went well.
            return create_json_response({"response": "Issue created successfully"})

    parameters = {
        "title": title,
        "description": issue_content,
        "labels": issueTypes[request_type] + "," + get_client_id_from_request(),
        "confidential": True,
    }

    if get_client_id_from_request() == "nfdi4chem" and not appError:
        adminIds = settings.NFDI4CHEM_GITLAB_ADMIN_IDS
        if adminIds:
            for id in adminIds.split(","):
                issue_content = "@{}\n\n".format(id) + issue_content
            parameters["description"] = issue_content

    headers = {
        "PRIVATE-TOKEN": settings.GITLAB_TS_USER_API_TOKEN,
        "Content-Type": "application/json",
    }
    url = settings.GITLAB_API_BASE_URL + "{}/issues".format(
        urllib.parse.quote(settings.CONTACT_REQUEST_RECEIVER_REPO, safe="")
    )
    response = requests.post(url, params=parameters, headers=headers)
    if response.status_code != 201:
        return HttpResponseServerError(
            "Failed to create issue. Please try again later."
        )

    return create_json_response({"response": "Issue created successfully"})


def appErrorExist(title):
    headers = {
        "PRIVATE-TOKEN": settings.GITLAB_TS_USER_API_TOKEN,
        "Content-Type": "application/json",
    }
    url = (
        settings.GITLAB_API_BASE_URL
        + "{}/issues?labels=Problem&state=opened&search={}&in=title".format(
            urllib.parse.quote(settings.CONTACT_REQUEST_RECEIVER_REPO, safe=""),
            title,
        )
    )
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        response = response.json()
        if not response:
            return False
        return True
    return True
