from user.models import UserModel, RoleModel
from user.libs.auth import Auth
from user_service.libs.decorators import (
    error_handler_decorator,
    authentication_required
)
from django.views.decorators.http import require_http_methods
from user_service.middlewares.request import (
    get_headers_dict,
    get_username_from_request,
    get_client_id_from_request
)
import json
from user_service.libs.utils import create_json_response
from note.models import NoteModel
from report.models import ReportModel
from github.models import GithubIssueRequestModel
from django.conf import settings
from django.http import Http404



@error_handler_decorator
@authentication_required
@require_http_methods(['POST'])
def is_entity_admin(request):
    auth_object_dict = get_headers_dict()
    client_ts = get_client_id_from_request()
    user = UserModel.objects.filter(username=get_username_from_request(), client_ts=client_ts).first()
    auth_object_dict['user_id'] = user.id
    auth_controller = Auth(**auth_object_dict)    

    _form = json.loads(request.body)
    ontologyId = _form.get('ontologyId')
    collectionId = _form.get('collectionId')
    return create_json_response({'is_admin': auth_controller.is_user_admin_for_entity(ontologyId=ontologyId, collectionId=collectionId)})




@error_handler_decorator
@authentication_required
@require_http_methods(['POST'])
def is_system_admin():    
    client_ts = get_client_id_from_request()
    user = UserModel.objects.filter(username=get_username_from_request(), client_ts=client_ts).first()
    
    role_model = RoleModel.objects.filter(user=user, client_ts=client_ts).first()
    is_admin = True if role_model.target_object_type == 'system' else False
    return create_json_response({'is_system_admin': is_admin})


@error_handler_decorator
@require_http_methods(["GET"])
def get_stats(request):
    header = get_headers_dict()
    if settings.STATS_API_TOKEN != header.get("access_token", "default"):
        raise Http404("not found")
    
    
    def calculate_stats(client_ts, stats):
        users = UserModel.objects.filter(client_ts=client_ts).all();
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
            report_count += len(ReportModel.objects.filter(reporter = u).all()) 
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

    client_ts = ["nfdi4chem", "general", "nfdi4ing"];
    stats = {}
    for cts in client_ts:
        stats[cts] = {}
        calculate_stats(cts, stats[cts])

    return create_json_response({"stats": stats})
