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



@error_handler_decorator
@authentication_required
@require_http_methods(['POST'])
def is_entity_admin(request):
    auth_object_dict = get_headers_dict()
    user = UserModel.objects.filter(username=get_username_from_request()).first()
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
    user = UserModel.objects.filter(username=get_username_from_request()).first()
    client_ts = get_client_id_from_request()
    
    role_model = RoleModel.objects.filter(user=user, client_ts=client_ts).first()
    is_admin = True if role_model.target_object_type == 'system' else False
    return create_json_response({'is_system_admin': is_admin})
