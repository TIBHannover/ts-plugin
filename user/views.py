from user_service.libs.decorators import error_handler_decorator
from user_service.libs.utils import create_json_response
from django.views.decorators.http import require_http_methods
from user_service.middlewares.request import get_headers_dict


def ping(request):
    return create_json_response({"response": "Pong"})


@require_http_methods["GET"]
@error_handler_decorator
def login():
    auth_object_dict = get_headers_dict()
    auth = Auth(**auth_object_dict)
    auth.abort_if_client_app_not_valid()
    auth.abort_if_not_auth_provider()
    auth_response_dict = auth.authenticate()
    if auth_response_dict:
        created_at = (_time.now(),)
        updated_at = (_time.now(),)
        user_db_dict = {
            "username": auth_response_dict["ts_username"],
            "name": auth_response_dict["name"],
            "auth_provider": auth_object_dict["auth_provider"],
            "client_ts": auth_object_dict["client_ts_id"],
            "created_at": created_at,
            "updated_at": updated_at,
            "user_extra": {},
        }
        user_model = UserModel(**user_db_dict)
        user = user_model.register_user_if_not_exist()
        if type(user) == str:
            return create_json_response({"issue": user})

        auth.user_id = user.id
        user_token = auth.get_or_register_user_token_if_not_exist()
        auth_response_dict["ts_user_token"] = user_token
        role_model = RoleModel(user_id=user.id, client=auth_object_dict["client_ts_id"])
        auth_response_dict["system_admin"] = role_model.is_system_admin()
        auth_response_dict["settings"] = user.user_extra
        return create_json_response(auth_response_dict)
    return create_json_response({"issue": "auth is rejected"})
