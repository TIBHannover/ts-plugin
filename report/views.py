from user_service.libs.utils import create_json_response
from user.models import UserModel, RoleModel
from .models import ReportModel
from datetime import datetime as _time
from note.models import NoteModel, NoteCommentModel
from user_service.libs.decorators import error_handler_decorator, authentication_required
from user_service.libs.email import Email
from user_service.middlewares.request import get_headers_dict 



DEFAULT_NOTE_LIST_SIZE = 10
DEFAULT_NOTE_LIST_PAGE = 1



@blueprint.route("/create_report", methods=["POST"])
@error_handler_decorator
@authentication_required
def create_report():
    object_type = request.form['objectType']
    object_id = request.form['objectId']
    content = request.form['content']
    ontologyId = request.form['ontology']

    creator_username = request.headers.get('X-TS-User-Name')
    user = UserModel.get_by_username(username=creator_username)
    client_id = AppRequestHeader.get_client_id() 

    report_dict = {
        "created_at": _time.now(),
        "reported_object_type": object_type,
        "reported_object_id": object_id,
        "reporter_id": user.id,
        "report_content": content,
        "client_ts": client_id
    }

    report_model = ReportModel(**report_dict)
    report_created = report_model.register_report()
    if report_created:
        try:
            subject = "Content Reported By the user"
            body = "This {} is reported by the user {}: \n\n".format(object_type, creator_username)
            body += "Report Message: \n"
            body += "{} \n\n URL: \n".format(content)
            reported_content_base_url = Utils.get_frontend_base_url()
            if object_type == "note":
                reported_content_base_url += "/ontologies/{}/notes?noteId={}".format(ontologyId, object_id)

            elif object_type == "comment":            
                comment = NoteCommentModel.get_by_id(object_id)
                reported_content_base_url += "/ontologies/{}/notes?noteId={}&comment={}".format(ontologyId, comment.note_id, object_id)
                    
            body += reported_content_base_url            
            body += "\n\n Please Check it as soon as possible."
            
            email = Email(subject=subject, body=body, client_ts=AppRequestHeader.get_client_id())
            email.report_content_to_admins()
        except Exception as e:
            print("Error while sending email for the created report: ", e)
        
    return Common.create_json_response({'report_created': report_created})




@blueprint.route("/resolve_report", methods=["POST"])
@error_handler_decorator
@authentication_required
def resolve_report():
    ''''
        Resolve action types: 
            - none (no action)
            - delete-block (delete the content and block the creator user)
            - delete (only delete the content)
    '''

    username = request.headers.get('X-TS-User-Name')
    client_ts = AppRequestHeader.get_client_id()
    user_id = UserModel.get_user_id_by_username(username=username)
    role_model = RoleModel(user_id=user_id, client=client_ts)
    if not role_model.is_system_admin():
        abort(401, "Not Authorized")
    
    object_type = request.form['objectType']
    object_id = request.form['objectId']
    action = request.form['action']   
    creator_username = request.form['creatorUsername'] 
    
    if action == "none":
        reports = ReportModel(reported_object_type=object_type, reported_object_id=object_id)
        reports.delete()
        return Common.create_json_response({'resolved': True})
    
    if action == "delete-block":        
        UserModel.block_user(username=creator_username)        
    
    if object_type == "note":
        note = NoteModel.get_by_id(object_id)
        if note and note.delete_record():
            ReportModel.resolve(object_type="note", object_id=object_id)            
            return Common.create_json_response({'resolved': True})
    
    if object_type == "comment":
        comment = NoteCommentModel.get_by_id(object_id)
        if comment and comment.delete_record():
            ReportModel.resolve(object_type="comment", object_id=object_id)            
            return Common.create_json_response({'resolved': True})
    

    return Common.create_json_response({'resolved': False})



@blueprint.route("/report_list", methods=["GET"])
@error_handler_decorator
@authentication_required
def report_list():
    username = request.headers.get('X-TS-User-Name')
    client_ts = AppRequestHeader.get_client_id()
    user_id = UserModel.get_user_id_by_username(username=username)
    role_model = RoleModel(user_id=user_id, client=client_ts)
    if not role_model.is_system_admin():
        abort(401, "Not Authorized")
    
    reports = ReportModel.get_pending_reports_for_client(client_id=client_ts)
    reports_list = []
    reported_content_base_url = Utils.get_frontend_base_url()
    for report in reports:
        rep_dict = {}
        rep_dict['reporter_username'] = UserModel.get_user_name_by_id(user_id=report.reporter_id)
        rep_dict['report_date'] = report.created_at
        rep_dict['report_reason'] = report.report_content
        if report.reported_object_type == "note":
            note = NoteModel.get_by_id(note_id=report.reported_object_id)            
            rep_dict['reported_content_type'] = 'note'
            rep_dict['reported_content_url'] = reported_content_base_url + "/ontologies/{}/notes?noteId={}".format(note.ontology_id, report.reported_object_id)

        elif report.reported_object_type == "comment":            
            comment = NoteCommentModel.get_by_id(report.reported_object_id)
            note = NoteModel.get_by_id(comment.note_id)
            rep_dict['reported_content_type'] = 'comment'
            rep_dict['reported_content_url'] = reported_content_base_url + "/ontologies/{}/notes?noteId={}&comment={}".format(note.ontology_id, comment.note_id, report.reported_object_id)

        reports_list.append(rep_dict)
    

    return Common.create_json_response({'reports': reports_list})




@blueprint.cli.command("send-reminder-report-email")
@error_handler_decorator
def send_reminer_report_email():
    pending_reports = ReportModel.get_all_pending_reports()
    frontends = Utils.get_frontends_metadata()
    email_subject = "Reminder for reported contents"
    for report in pending_reports:        
        reporter_username = UserModel.get_user_name_by_id(user_id=report.reporter_id)
        body = "This {} is reported by the user {}: \n\n".format(report.reported_object_type, reporter_username)
        body += "Report Message: \n"
        body += "{} \n\n URL: \n".format(report.report_content)        
        if report.reported_object_type == "note":
            note = NoteModel.get_by_id(note_id=report.reported_object_id)
            reported_content_base_url = frontends[note.client_ts]['base_url']
            reported_content_base_url += "/ontologies/{}/notes?noteId={}".format(note.ontology_id, report.reported_object_id)

        elif report.reported_object_type == "comment":            
            comment = NoteCommentModel.get_by_id(report.reported_object_id)
            note = NoteModel.get_by_id(comment.note_id)
            reported_content_base_url = frontends[note.client_ts]['base_url']
            reported_content_base_url += "/ontologies/{}/notes?noteId={}&comment={}".format(note.ontology_id, comment.note_id, report.reported_object_id)
                
        body += reported_content_base_url            
        body += "\n -------------------------------- \n"

    for client_ts_id, value in frontends.items():
        email = Email(subject=email_subject, body=body, client_ts=client_ts_id)
        email.report_content_to_admins()
    
    print("Reminder email has been sent to all system admins.")

   
    


   

