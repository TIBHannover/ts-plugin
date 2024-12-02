from user_service.libs.decorators import error_handler_decorator
import requests
import urllib.parse
from user_service.middlewares.request import get_client_id_from_request
from django.views.decorators.http import require_http_methods
from user_service.libs.utils import create_json_response
from django.http import HttpResponseBadRequest, HttpResponseServerError
from django.conf import settings


@require_http_methods(['GET'])
def ping(request):
    return create_json_response({"response": "Pong"})


@error_handler_decorator
@require_http_methods(['POST'])
def create(request):
    data = request.json()
    issueTypes = {"1": "Question", "2": "Problem"}

    title = data["title"]
    description = data["description"]
    email = data["email"]
    name = data["name"]
    type = data["type"]
    safeQuestion = data["safeQuestion"]
    safeAnswer = data["safeAnswer"]

    safeNumbers = safeQuestion.split("+")
    if len(safeNumbers) != 2 or int(safeNumbers[0]) + int(safeNumbers[1]) != int(safeAnswer):
        return HttpResponseBadRequest("Invalid safe question and answer.")

    issue_content = "from: {} ({})\n\n{}".format(name, email, description)

    parameters = {
        "title": title,
        "description": issue_content,
        "labels": issueTypes[type],
        "confidential": True,
    }

    if get_client_id_from_request() == "nfdi4chem":
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
        urllib.parse.quote(
            settings.CONTACT_REQUEST_RECEIVER_REPO, safe=""
        )
    )
    response = requests.post(url, params=parameters, headers=headers)
    if response.status_code != 201:
        return HttpResponseServerError("Failed to create issue. Please try again later.")

    return create_json_response({"response": "Issue created successfully"})
