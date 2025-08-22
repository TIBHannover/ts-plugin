from django.shortcuts import HttpResponse
from django.core.exceptions import PermissionDenied, BadRequest
from django.http import Http404, JsonResponse
from user_service.middlewares.request import get_headers_dict, get_request_method, get_username_from_request
from user.models import UserModel
from user.libs.auth import Auth


def authentication_required(func):
    def wrapper(*args, **kwargs):
        auth_object_dict = get_headers_dict()
        if get_request_method() != "OPTIONS":
            user_id = UserModel.get_user_id_by_username(
                username=get_username_from_request()
            )
            auth_object_dict["user_id"] = user_id
            auth_controller = Auth(**auth_object_dict)
            auth_controller.abort_if_not_authenticated()
        return func(*args, **kwargs)

    wrapper.__name__ = func.__name__
    return wrapper


def error_handler_decorator(func):
    def wrapp_this_function(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            return result
        except KeyError as e:
            # if current_app.config.get('DEBUG_MODDE'):
            # raise
            print("Mandatory Fields are missing : " + str(e), flush=True)
            response = HttpResponse(
                "Mandatory Fields are missing : " + str(e),
                status=400,
                content_type="text/plain",
            )
            return response

        except PermissionDenied as e:
            print(e)
            response = HttpResponse(str(e), status=401)
            return response

        except BadRequest as e:
            response = HttpResponse(str(e), status=400)
            return response

        except Http404 as e:
            return JsonResponse({"_result": str(e)}, status=404)

        # except HTTPException as e:
        #     # if current_app.config.get("DEBUG_MODDE"):
        #     # raise
        #     response = HttpResponse(e.get_response(), status=e.code)
        #     # logging.debug(e.get_response())
        #     print(e.get_response(), flush=True)
        #     return response

        except Exception as e:
            # raise
            # if current_app.config.get("DEBUG_MODDE"):
            # raise
            # logging.error(e)
            raise
            print(e, flush=True)
            response = HttpResponse(
                str(e),
                status=500,
                content_type="text/plain",
            )
            return response

    wrapp_this_function.__name__ = func.__name__
    return wrapp_this_function
