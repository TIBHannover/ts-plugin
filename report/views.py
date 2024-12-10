from requests import request
from user_service.libs.utils import create_json_response
from user.models import UserModel, RoleModel
from .models import ReportModel
from datetime import datetime as _time
from note.models import NoteModel, NoteCommentModel
from user_service.libs.decorators import error_handler_decorator, authentication_required
from user_service.libs.email import Email
from user_service.libs.utils import get_frontend_base_url 
from user_service.middlewares.request import get_headers_dict, get_username_from_request, get_client_id_from_request
from django.views.decorators.http import require_http_methods
import json
from django.core.exceptions import PermissionDenied



DEFAULT_NOTE_LIST_SIZE = 10
DEFAULT_NOTE_LIST_PAGE = 1



@error_handler_decorator
@authentication_required
@require_http_methods(['POST'])
def create_report(request):
    _form = json.loads(request.body)
    object_type = _form['objectType']
    object_id = _form['objectId']
    content = _form['content']
    ontologyId = _form['ontology']

    creator_username = get_username_from_request()
    client_id = get_client_id_from_request()
    user = UserModel.objects.filter(username=creator_username, client_ts=client_id).first()

    report_dict = {
        "created_at": _time.now(),
        "reported_object_type": object_type,
        "reported_object_id": object_id,
        "reporter_id": user.id,
        "report_content": content,
        "client_ts": client_id
    }

    report_model = ReportModel(**report_dict)
    report_model.save()
    try:
        subject = "Content Reported By the user"
        body = "This {} is reported by the user {}: \n\n".format(object_type, creator_username)
        body += "Report Message: \n"
        body += "{} \n\n URL: \n".format(content)
        reported_content_base_url = get_frontend_base_url()
        if object_type == "note":
            reported_content_base_url += "/ontologies/{}/notes?noteId={}".format(ontologyId, object_id)

        elif object_type == "comment":            
            comment = NoteCommentModel.objects.get(id=object_id)
            reported_content_base_url += "/ontologies/{}/notes?noteId={}&comment={}".format(ontologyId, comment.note_id, object_id)
                
        body += reported_content_base_url            
        body += "\n\n Please Check it as soon as possible."
        
        email = Email(subject=subject, body=body, client_ts=client_id)
        email.report_content_to_admins()
    except Exception as e:
        print("Error while sending email for the created report: ", e)
        
    return create_json_response({'report_created': True})




@error_handler_decorator
@authentication_required
@require_http_methods(['POST'])
def resolve_report(request):
    ''''
        Resolve action types: 
            - none (no action)
            - delete-block (delete the content and block the creator user)
            - delete (only delete the content)
    '''

    username = get_username_from_request()
    client_ts = get_client_id_from_request()
    role_model = RoleModel.objects.filter(user__username=username, client_ts=client_ts, target_object_type="system", role="admin").first()
    if not role_model:
        raise PermissionDenied("Not Authorized")
    
    _form = json.loads(request.body)
    object_type = _form['objectType']
    object_id = _form['objectId']
    action = _form['action']   
    creator_username = _form['creatorUsername'] 
    
    if action == "none":
        reports = ReportModel.objects.filter(reported_object_type=object_type, reported_object_id=object_id)
        reports.delete()
        return create_json_response({'resolved': True})
    
    if action == "delete-block":        
        UserModel.block_user(username=creator_username)        
    
    if object_type == "note":
        note = NoteModel.objects.filter(id=object_id).first()
        if note:
            note.delete()
            reports = ReportModel.objects.filter(reported_object_type="note", reported_object_id=object_id)
            for rep in reports:
                rep.resolve()
            return create_json_response({'resolved': True})
    
    if object_type == "comment":
        comment = NoteCommentModel.objects.filter(id=object_id).first()
        if comment:
            comment.delete()
            reports = ReportModel.objects.filter(reported_object_type="comment", reported_object_id=object_id)
            for rep in reports:
                rep.resolve()
            return create_json_response({'resolved': True})
    

    return create_json_response({'resolved': False})



@error_handler_decorator
@authentication_required
@require_http_methods(['GET'])
def report_list(request):
    username = get_username_from_request()
    client_ts = get_client_id_from_request()
    role_model = RoleModel.objects.filter(user__username=username, client_ts=client_ts, target_object_type="system", role="admin").first()
    if not role_model:
        raise PermissionDenied("Not Authorized")
    
    reports = ReportModel.get_pending_reports_for_client(client_id=client_ts)
    reports_list = []
    reported_content_base_url = get_frontend_base_url()
    for report in reports:
        rep_dict = {}
        rep_dict['reporter_username'] = UserModel.get_user_name_by_id(user_id=report.reporter_id)
        rep_dict['report_date'] = report.created_at
        rep_dict['report_reason'] = report.report_content
        if report.reported_object_type == "note":
            note = NoteModel.objects.get(id=report.reported_object_id)            
            rep_dict['reported_content_type'] = 'note'
            rep_dict['reported_content_url'] = reported_content_base_url + "/ontologies/{}/notes?noteId={}".format(note.ontology_id, report.reported_object_id)

        elif report.reported_object_type == "comment":            
            comment = NoteCommentModel.objects.get(id=report.reported_object_id)
            note = comment.note
            rep_dict['reported_content_type'] = 'comment'
            rep_dict['reported_content_url'] = reported_content_base_url + "/ontologies/{}/notes?noteId={}&comment={}".format(note.ontology_id, comment.note_id, report.reported_object_id)

        reports_list.append(rep_dict)
    

    return create_json_response({'reports': reports_list})




# @blueprint.cli.command("send-reminder-report-email")
# @error_handler_decorator
# def send_reminer_report_email():
#     pending_reports = ReportModel.get_all_pending_reports()
#     frontends = Utils.get_frontends_metadata()
#     email_subject = "Reminder for reported contents"
#     for report in pending_reports:        
#         reporter_username = UserModel.get_user_name_by_id(user_id=report.reporter_id)
#         body = "This {} is reported by the user {}: \n\n".format(report.reported_object_type, reporter_username)
#         body += "Report Message: \n"
#         body += "{} \n\n URL: \n".format(report.report_content)        
#         if report.reported_object_type == "note":
#             note = NoteModel.get_by_id(note_id=report.reported_object_id)
#             reported_content_base_url = frontends[note.client_ts]['base_url']
#             reported_content_base_url += "/ontologies/{}/notes?noteId={}".format(note.ontology_id, report.reported_object_id)
#
#         elif report.reported_object_type == "comment":            
#             comment = NoteCommentModel.get_by_id(report.reported_object_id)
#             note = NoteModel.get_by_id(comment.note_id)
#             reported_content_base_url = frontends[note.client_ts]['base_url']
#             reported_content_base_url += "/ontologies/{}/notes?noteId={}&comment={}".format(note.ontology_id, comment.note_id, report.reported_object_id)
#
#         body += reported_content_base_url            
#         body += "\n -------------------------------- \n"
#
#     for client_ts_id, value in frontends.items():
#         email = Email(subject=email_subject, body=body, client_ts=client_ts_id)
#         email.report_content_to_admins()
#
#     print("Reminder email has been sent to all system admins.")

   
    


   

