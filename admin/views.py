from user.models import UserModel, RoleModel
from user.libs.auth import Auth
from user_service.libs.decorators import (
    error_handler_decorator,
    authentication_required,
)
from django.views.decorators.http import require_http_methods
from user_service.middlewares.request import (
    get_headers_dict,
    get_username_from_request,
    get_client_id_from_request,
)
import json
from user_service.libs.utils import create_json_response
from note.models import NoteModel
from report.models import ReportModel
from github.models import GithubIssueRequestModel
from django.conf import settings
from django.http import Http404
import urllib.parse
import requests
from django.http import JsonResponse


@error_handler_decorator
@authentication_required
@require_http_methods(["POST"])
def is_entity_admin(request):
    auth_object_dict = get_headers_dict()
    client_ts = get_client_id_from_request()
    user = UserModel.objects.filter(
        username=get_username_from_request(), client_ts=client_ts
    ).first()
    auth_object_dict["user_id"] = user.id
    auth_controller = Auth(**auth_object_dict)

    _form = json.loads(request.body)
    ontologyId = _form.get("ontologyId")
    collectionId = _form.get("collectionId")
    return create_json_response(
        {
            "is_admin": auth_controller.is_user_admin_for_entity(
                ontologyId=ontologyId, collectionId=collectionId
            )
        }
    )


@error_handler_decorator
@authentication_required
@require_http_methods(["POST"])
def is_system_admin():
    client_ts = get_client_id_from_request()
    user = UserModel.objects.filter(
        username=get_username_from_request(), client_ts=client_ts
    ).first()

    role_model = RoleModel.objects.filter(user=user, client_ts=client_ts).first()
    is_admin = True if role_model.target_object_type == "system" else False
    return create_json_response({"is_system_admin": is_admin})


@error_handler_decorator
@require_http_methods(["GET"])
def get_stats(request):
    args = request.GET
    project_id = args.get("project_id")
    header = get_headers_dict()
    if settings.STATS_API_TOKEN != header.get("access_token", "default"):
        raise Http404("not found")

    headers = {
        "PRIVATE-TOKEN": settings.GITLAB_TS_USER_API_TOKEN,
        "Content-Type": "application/json",
    }

    def calculate_stats(client_ts, stats):
        users = UserModel.objects.filter(client_ts=client_ts).all()
        stats["user_count"] = len(users)
        note_count = 0
        comment_count = 0
        collection_count = 0
        termset_count = 0
        report_count = 0
        github_issues_count = 0
        term_request_count = 0
        for u in users:
            user_notes = NoteModel.objects.filter(creator=u).all()
            note_count += len(user_notes)
            comment_count += len(u.user_comments.all())
            collection_count += len(u.user_collections.all())
            termset_count += len(u.user_term_sets.all())
            report_count += len(ReportModel.objects.filter(reporter=u).all())
            github_issues = GithubIssueRequestModel.objects.filter(user=u).all()
            for gi in github_issues:
                if gi.issue_type == "termRequest":
                    term_request_count += 1
                else:
                    github_issues_count += 1

        stats["note_count"] = note_count
        stats["comment_count"] = comment_count
        stats["collection_count"] = collection_count
        stats["termset_count"] = termset_count
        stats["report_count"] = report_count
        stats["github_issues_count"] = github_issues_count
        stats["term_request_count"] = term_request_count

    def calculate_gitlab_stats(client_ts, stats):
        # ontology suggestion and contact form
        url = settings.GITLAB_API_BASE_URL + "{}/issues".format(
            urllib.parse.quote(settings.ONTOLOGY_SUGGESTION_REPO, safe="")
        )

        resp = requests.get(url, headers=headers)
        ontology_suggestion_count = 0
        for iss in resp.json():
            if client_ts == "general" and "ontology_suggestion" in iss["labels"]:
                ontology_suggestion_count += 1
            elif (
                "ontology_suggestion" in iss["labels"]
                and client_ts.upper() in iss["labels"]
            ):
                ontology_suggestion_count += 1
        stats["ontology_suggestion_count"] = ontology_suggestion_count

        url = settings.GITLAB_API_BASE_URL + "{}/issues".format(
            urllib.parse.quote(settings.CONTACT_REQUEST_RECEIVER_REPO, safe="")
        )
        resp = requests.get(url, headers=headers)
        contact_form_count = 0
        for iss in resp.json():
            if client_ts in iss["labels"]:
                contact_form_count += 1

        stats["contact_form_count"] = contact_form_count

    client_ts = ["nfdi4chem", "general", "nfdi4ing"]
    if project_id.lower() not in client_ts:
        raise Http404("not found")

    stats = {}
    calculate_stats(project_id, stats)
    calculate_gitlab_stats(project_id, stats)

    return JsonResponse(stats)
