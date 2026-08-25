from django.shortcuts import HttpResponse
from django.core.exceptions import PermissionDenied, BadRequest
from django.conf import settings
from django.http import Http404, JsonResponse
from user_service.middlewares.request import (
    get_headers_dict,
    get_request_method,
    get_username_from_request,
    get_api_key_from_request,
)
from user.models import UserModel
from user.libs.auth import Auth
from user_service.middlewares.request import is_csrf_valid
from user_service.libs.utils import make_hash


def authentication_required(func):
    def wrapper(*args, **kwargs):
        if get_request_method() != "OPTIONS":
            api_key = get_api_key_from_request()
            if api_key:
                # this is an api call
                user = UserModel.objects.filter(api_key=make_hash(api_key)).first()
                if user:
                    return func(*args, **kwargs)
                else:
                    raise PermissionDenied("Not Authorized")
            auth_object_dict = get_headers_dict()
            user_id = UserModel.get_user_id_by_username(
                username=get_username_from_request()
            )
            auth_object_dict["user_id"] = user_id
            auth_controller = Auth(**auth_object_dict)
            if not is_csrf_valid():
                raise PermissionDenied("request is not valid")
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
            if settings.DEBUG:
                raise
            print("Mandatory Fields are missing : " + str(e), flush=True)
            response = HttpResponse(
                "Mandatory Fields are missing : " + str(e),
                status=400,
                content_type="text/plain",
            )
            return response

        except PermissionDenied as e:
            if settings.DEBUG:
                raise
            print(e)
            response = HttpResponse(str(e), status=401)
            return response

        except BadRequest as e:
            if settings.DEBUG:
                raise
            response = HttpResponse(str(e), status=400)
            return response

        except Http404 as e:
            if settings.DEBUG:
                raise
            return JsonResponse({"_result": str(e)}, status=404)

        except Exception as e:
            if settings.DEBUG:
                raise
            response = HttpResponse(
                str(e),
                status=500,
                content_type="text/plain",
            )
            return response

    wrapp_this_function.__name__ = func.__name__
    return wrapp_this_function
