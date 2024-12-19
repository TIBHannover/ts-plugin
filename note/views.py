import user
from user_service.libs.utils import (
    create_json_response, 
    add_to_dict_if_value_is_not_none, 
    get_int_from_string
)
from user.models import UserModel
from user.libs.auth import Auth
from datetime import datetime as _time
from .models import NoteModel, NoteCommentModel
from report.models import ReportModel
from user_service.libs.decorators import (
    error_handler_decorator,
    authentication_required,
    client_id_validation,
)
import math
from django.views.decorators.http import require_http_methods
from user_service.middlewares.request import get_client_id_from_request, get_headers_dict, get_username_from_request
from django.http import HttpResponseServerError, Http404, HttpResponseBadRequest
from django.core.exceptions import PermissionDenied
from django.conf import settings
import json


DEFAULT_NOTE_LIST_SIZE = 10
DEFAULT_NOTE_LIST_PAGE = 1


require_http_methods(['GET'])
def ping(request):
    return create_json_response({"response": "Pong"})


@error_handler_decorator
@authentication_required
@require_http_methods(['POST'])
def create(request):
    print(request.body)
    payload = json.loads(request.body)
    frontend_id = get_client_id_from_request()
    creator_username = get_username_from_request()
    title = payload["title"]
    content = payload["content"]
    ontology_id = payload["ontology_id"]
    semantic_component_type = payload["semantic_component_type"]
    semantic_component_iri = payload["semantic_component_iri"]
    semantic_component_label = payload["semantic_component_label"]
    visibility = payload.get("visibility", "me")
    parent_ontology = payload.get("parentOntology")
    if visibility.lower() not in ["me", "internal", "public"]:
        visibility = "me"

    user = UserModel.objects.filter(username=creator_username).first()

    note_model_record_dict = {
        "creator_id": user.id,
        "created_at": _time.now(),
        "ontology_id": ontology_id.lower(),
        "content": content,
        "title": title,
        "semantic_component_type": semantic_component_type.lower(),
        "client_ts": frontend_id.lower(),
        "semantic_component_iri": semantic_component_iri,
        "semantic_component_label": semantic_component_label,
        "visibility": visibility,
        "parent_ontology_id": parent_ontology,
    }
    note_model_object = NoteModel(**note_model_record_dict)
    note_model_object.save()
    if not note_model_object.id:
        return HttpResponseServerError("Something went wrong.")
    return create_json_response({"note_created": note_model_object.to_dict()})


@error_handler_decorator
@authentication_required
@require_http_methods(['PUT'])
def update(request):
    payload = json.loads(request.body)
    frontend_id = get_client_id_from_request()
    noteId = payload["noteId"]
    title = payload.get("title")
    content = payload.get("content")
    ontology_id = payload.get("ontology_id")
    semantic_component_type = payload.get("semantic_component_type")
    semantic_component_iri = payload.get("semantic_component_iri")
    semantic_component_label = payload.get("semantic_component_label")
    visibility = payload.get("visibility", "me")
    parent_ontology = payload.get("parentOntology")

    if visibility.lower() not in ["me", "internal", "public"]:
        visibility = "me"  

    updates = {}
    updates["updated_at"] = _time.now()
    updates["parent_ontology_id"] = parent_ontology
    add_to_dict_if_value_is_not_none(updates, "ontology_id", ontology_id)
    add_to_dict_if_value_is_not_none(updates, "title", title)
    add_to_dict_if_value_is_not_none(updates, "content", content)
    add_to_dict_if_value_is_not_none(updates, "semantic_component_type", semantic_component_type)
    add_to_dict_if_value_is_not_none(updates, "semantic_component_iri", semantic_component_iri)
    add_to_dict_if_value_is_not_none(updates, "semantic_component_label", semantic_component_label)
    add_to_dict_if_value_is_not_none(updates, "visibility", visibility)

    note_to_update = NoteModel.objects.filter(id=noteId).first()
    if not note_to_update:
        raise Http404("Note does not exist.")

    username = get_username_from_request()
    user = UserModel.objects.filter(username=username).first()

    _auth = Auth(user_id=user.id, client_ts_id=frontend_id)
    can_edit = _auth.user_can_edit_object(
        objectModel=NoteModel, object_id=noteId, role_target_object_id=ontology_id
    )
    if not can_edit:
        raise PermissionDenied("Not Authorized")

    upadated_note = note_to_update.update_record(updates=updates)

    return create_json_response({"note_updated": upadated_note.to_dict()})


@error_handler_decorator
@client_id_validation
@require_http_methods(['GET'])
def list(request):
    args = request.GET
    ontology_id = args.get("ontology")
    target_iri = args.get("artifact_iri")
    target_type = args.get("artifact_type")
    size = args.get("size")
    page = args.get("page")
    get_notes_from_children = True if not args.get("onlyOriginalNotes") else False
    size = get_int_from_string(size)
    page = get_int_from_string(page)
    if not size:
        size = DEFAULT_NOTE_LIST_SIZE
    if not page:
        page = DEFAULT_NOTE_LIST_PAGE

    auth_object_dict = get_headers_dict()
    user_id = UserModel.get_user_id_by_username(username=auth_object_dict["username"])
    auth_object_dict["user_id"] = user_id
    auth = Auth(**auth_object_dict)

    visibilities = ["public"]

    if not auth.user_is_guest():
        visibilities.append("internal")

    else:
        user_id = -1

    note_list_conditions = {}
    note_list_conditions["client_ts"] = auth_object_dict["client_ts_id"]
    note_list_conditions["ontology_id"] = ontology_id
    note_list_conditions["visibilities"] = visibilities
    note_list_conditions["user_id"] = user_id
    note_list_conditions["get_notes_from_children"] = False
    note_list_conditions["pinned"] = True
    
    pinned_notes = []
    if not target_iri:
        # For the general note list, we need pinned ones. For iri-specific notes, pinned are not needed.
        pinned_notes = NoteModel.get_notes_by_conditions(note_list_conditions)["notes"]

    size_without_pinned = int(size) - len(pinned_notes)

    note_list_conditions["pinned"] = False
    note_list_conditions["semantic_component_type"] = target_type
    note_list_conditions["get_notes_from_children"] = get_notes_from_children
    note_list_conditions["semantic_component_iri"] = target_iri
    note_list_conditions["offset"] = (page - 1) * size_without_pinned
    note_list_conditions["limit"] = size
    notes_and_stats = NoteModel.get_notes_by_conditions(note_list_conditions)
    notes = notes_and_stats["notes"]

    notes = pinned_notes + notes
    for note in notes:
        note_report = ReportModel.objects.filter(reported_object_type="note", reported_object_id=note["id"]).first()
        note["can_edit"] = auth.user_can_edit_object(
            objectModel=NoteModel,
            object_id=note["id"],
            role_target_object_id=ontology_id,
        )
        note["is_reported"] = True if note_report else False

    notes_total_count = notes_and_stats["count_of_all_notes"]
    stats = {}
    stats["number_of_pinned"] = len(pinned_notes)
    stats["page"] = page
    stats["size"] = size
    stats["total_number_of_records"] = notes_total_count + len(pinned_notes)
    stats["totalPageCount"] = math.ceil(notes_total_count / size)

    return create_json_response({"notes": notes, "stats": stats})


@error_handler_decorator
@client_id_validation
@require_http_methods(['GET'])
def get(request, note_id):
    args = request.GET
    with_comments = args.get("withComments")
    ontology_id = args.get("ontology")
    auth_object_dict = get_headers_dict()
    user_id = UserModel.get_user_id_by_username(username=auth_object_dict["username"])
    auth_object_dict["user_id"] = user_id
    _auth = Auth(**auth_object_dict)
    client_id = get_client_id_from_request() 
    try:
        _auth.abort_if_user_token_is_not_valid()
    except:
        user_id = -1

    note = NoteModel.objects.filter(id=note_id).first()
    if not note:
        raise Http404("Note does not exist")

    _auth.user_id = user_id
    can_edit = _auth.user_can_edit_object(
        objectModel=NoteModel,
        object_id=note.id,
        role_target_object_id=note.ontology_id,
    )
    if not note.can_visit(user_id=user_id, client_ts=client_id, is_guest=_auth.user_is_guest()):
        raise Http404("Note does not exist")

    
    note_report_count = ReportModel.objects.filter(
        reported_object_type="note", reported_object_id=note.id
    ).count()
    note_dict = note.to_dict()
    note_dict["is_reported"] = True if note_report_count > 0 else False
    note_dict["can_edit"] = can_edit
    note_dict["imported"] = False if ontology_id == note.ontology_id else True
    if with_comments:
        note_dict['comments'] = []
        for comment in note.note_comments.all():
            comment_dict = comment.to_dict()
            comment_report_count = ReportModel.objects.filter(
                reported_object_type="comment", reported_object_id=comment.id
            ).count()
            comment_dict["is_reported"] = True if comment_report_count > 0 else False
            comment_dict["can_edit"] = _auth.user_can_edit_object(
                objectModel=NoteCommentModel,
                object_id=comment.id,
                role_target_object_id=note.ontology_id,
            )
            note_dict["comments"].append(comment_dict)

    note_list_conditions = {}
    note_list_conditions["client_ts"] = auth_object_dict["client_ts_id"]
    note_list_conditions["ontology_id"] = ontology_id
    note_list_conditions["visibilities"] = ["public", "internal"]
    note_list_conditions["user_id"] = user_id
    note_list_conditions["pinned"] = True
    number_of_pinned = NoteModel.get_notes_by_conditions(note_list_conditions)[
        "count_of_all_notes"
    ]
    return create_json_response(
        {"note": note_dict, "number_of_pinned": number_of_pinned}
    )


@error_handler_decorator
@authentication_required
@require_http_methods(['POST'])
def create_comment(request):
    payload = json.loads(request.body)
    auth_object_dict = get_headers_dict()
    note_id = payload["noteId"]
    content = payload["content"]
    user = UserModel.objects.filter(username=get_username_from_request()).first()
    auth_object_dict["user_id"] = user.id
    _auth = Auth(**auth_object_dict)

    note = NoteModel.objects.filter(id=note_id).first()
    client_id = get_client_id_from_request()
    if not note or not note.can_visit(user_id=user.id, client_ts=client_id, is_guest=_auth.user_is_guest()):
        raise Http404("Note does not exist")

    note_comment_record_dict = {
        "creator": user,
        "created_at": _time.now(),
        "content": content,
        "note": note,
    }

    note_comment_model = NoteCommentModel(**note_comment_record_dict)
    note_comment_model.save()
    if not note_comment_model.id:
        return HttpResponseServerError("Something went wrong.")

    return create_json_response({"comment_created": note_comment_model.to_dict()})


@error_handler_decorator
@authentication_required
@require_http_methods(['PUT'])
def update_comment(request):
    payload = json.loads(request.body)
    frontend_id = get_client_id_from_request()
    username = get_username_from_request()
    content = payload.get("content")
    comment_id = payload["comment_id"]
    ontology_id = payload["ontology_id"]
    user = UserModel.objects.filter(username=username).first()
    updates = {}
    updates["updated_at"] = _time.now()
    add_to_dict_if_value_is_not_none(updates, "content", content)

    comment_to_update = NoteCommentModel.objects.filter(id=comment_id).first()
    if not comment_to_update:
        raise Http404("Comment does not exist.")

    _auth = Auth(user_id=user.id, client_ts_id=frontend_id)
    can_edit = _auth.user_can_edit_object(
        objectModel=NoteCommentModel,
        object_id=comment_id,
        role_target_object_id=ontology_id,
    )
    if not can_edit:
        raise PermissionDenied("Not Authorized")

    comment_to_update.update_record(updates=updates)
    return create_json_response({"comment_updated": comment_to_update.to_dict()})


@error_handler_decorator
@authentication_required
@require_http_methods(['DELETE'])
def delete(request):
    payload = json.loads(request.body)
    frontend_id = get_client_id_from_request()
    username = get_username_from_request()
    object_id = payload["objectId"]
    object_type = payload["objectType"]
    ontology_id = payload["ontology_id"]
    user = UserModel.objects.filter(username=username).first()
    objectModel = NoteModel
    if object_type != "note":
        objectModel = NoteCommentModel
    _auth = Auth(user_id=user.id, client_ts_id=frontend_id)
    can_edit = _auth.user_can_edit_object(
        objectModel=objectModel,
        object_id=object_id,
        role_target_object_id=ontology_id,
    )

    if not can_edit:
        raise PermissionDenied("Not Authorized")

    object = objectModel.objects.filter(id=object_id).first()
    if not object:
        raise Http404("Object not found")
    object.delete()
    return create_json_response({"deleted": not object.active})
    


@error_handler_decorator
@authentication_required
@require_http_methods(['PUT'])
def update_pin(request):
    payload = json.loads(request.body)
    auth_object_dict = get_headers_dict()
    ontology_id = payload.get("ontology")
    note_id = payload.get("note_id")
    pinned = payload.get("pinned")
    username = get_username_from_request()
    user = UserModel.objects.filter(username=username).first()
    auth_object_dict["user_id"] = user.id
    auth = Auth(**auth_object_dict)
    if not auth.is_user_admin_for_entity(ontologyId=ontology_id):
        raise PermissionDenied("Not Authorized")

    if pinned not in ["true", "false"]:
        return HttpResponseBadRequest("Bad Request. pinned value has to be boolean.")

    pinned = True if pinned == "true" else False
    pinned_notes_conditions = {}
    pinned_notes_conditions["client_ts"] = auth_object_dict["client_ts_id"]
    pinned_notes_conditions["ontology_id"] = ontology_id
    pinned_notes_conditions["visibilities"] = ["public", "internal"]
    pinned_notes_conditions["user_id"] = user.id
    pinned_notes_conditions["pinned"] = True
    existing_pinned_count = NoteModel.get_notes_by_conditions(pinned_notes_conditions)[
        "count_of_all_notes"
    ]
    if pinned and existing_pinned_count == int(settings.MAX_PIN_NOTES):
        return HttpResponseBadRequest("Not possible to pin more notes for this ontology.")

    updates = {"pinned": pinned}
    note_to_update = NoteModel.objects.filter(id=note_id).first()
    if not note_to_update:
        raise Http404("Note does not exist.")

    if note_to_update.visibility == "me":
        return HttpResponseBadRequest("Bad request: Private notes cannot be pinned.")

    note_to_update.update_record(updates=updates)
    return create_json_response({"note_pinned": note_to_update.to_dict()})
