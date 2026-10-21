from user.models import UserModel, RoleModel
from user_service.libs.decorators import (
    error_handler_decorator,
    authentication_required,
)
from django.views.decorators.http import require_http_methods
from user_service.middlewares.request import (
    get_headers_dict,
    get_username_from_request,
)
from user_service.middlewares.client_id import get_client_id_from_request
import json
from user_service.libs.utils import create_json_response
from user_service.middlewares.request import get_access_token_for_stats
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Gauge
from django.http import HttpResponse, Http404
from admin.stats import Stats
from user_service import settings
from note.models import NoteModel
from report.models import ReportModel
from github.models import GithubIssueRequestModel
import urllib.parse
import requests
from django.http import JsonResponse
from django.core.exceptions import BadRequest
from user_service.libs.email import Email

app_stats_gauge = Gauge(
    "ts_plugin_stats",
    "TS-Plugin service stats",
    ["key"],
)


@error_handler_decorator
@authentication_required
@require_http_methods(["POST"])
def is_entity_admin(request):
    auth_object_dict = get_headers_dict()
    user = UserModel.get_by_username(username=get_username_from_request())
    auth_object_dict["user_id"] = user.id
    _form = json.loads(request.body)
    ontologyId = _form.get("ontologyId")
    collectionId = _form.get("collectionId")

    for key, value in user.get_user_admin_roles().items():
        if ontologyId in value:
            return create_json_response({"is_admin": True})
        if collectionId in value:
            return create_json_response({"is_admin": True})
        if key == "system" and len(value) > 0:
            return create_json_response({"is_admin": True})

    return create_json_response({"is_admin": False})


@error_handler_decorator
@authentication_required
@require_http_methods(["POST"])
def is_system_admin(request):
    client_ts = get_client_id_from_request()
    is_admin = RoleModel.objects.filter(
        user__username=get_username_from_request(),
        user__client_ts=client_ts,
        user__is_active=True,
        user__is_blocked=False,
        client_ts=client_ts,
        target_object_id="system",
        target_object_type="system",
        role="admin",
    ).exists()
    return create_json_response({"is_system_admin": is_admin})


@error_handler_decorator
@authentication_required
@require_http_methods(["POST"])
def send_test_email(request):
    client_ts = get_client_id_from_request()
    role = RoleModel.objects.filter(
        user__username=get_username_from_request(),
        user__client_ts=client_ts,
        user__is_active=True,
        user__is_blocked=False,
        client_ts=client_ts,
        target_object_id="system",
        target_object_type="system",
        role="admin",
    ).first()
    if not role:
        return JsonResponse({"_result": "System admin access required"}, status=403)
    if not role.role_holder_email:
        raise BadRequest("No email address configured for your system admin role")

    logs = Email(
        subject="TS Plugin test email",
        body="This is a test email from the TS Plugin service.",
        client_ts=client_ts,
    ).send([role.role_holder_email], notification_type="test_email")
    logs[0].refresh_from_db()
    if logs[0].status == "failed":
        return JsonResponse({"_result": "Could not queue test email"}, status=503)
    return JsonResponse(
        {"_result": {"email_log_id": logs[0].pk, "status": logs[0].status}},
        status=202,
    )


@error_handler_decorator
@require_http_methods(["GET"])
def metrics(request):
    if (
        not settings.STATS_API_TOKEN
        or settings.STATS_API_TOKEN != get_access_token_for_stats()
    ):
        raise Http404("not found")
    stats = Stats(gauge=app_stats_gauge)
    stats.run()
    return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)


@error_handler_decorator
@require_http_methods(["GET"])
def get_stats(request):
    args = request.GET
    project_id = args.get("project_id")
    if settings.STATS_API_TOKEN != get_access_token_for_stats():
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
