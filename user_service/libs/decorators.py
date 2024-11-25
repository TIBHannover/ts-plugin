from django.http import HttpResponse, HTTPException


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

        except HTTPException as e:
            # if current_app.config.get("DEBUG_MODDE"):
            # raise
            response = HttpResponse(e.get_response(), status=e.code)
            # logging.debug(e.get_response())
            print(e.get_response(), flush=True)
            return response

        except Exception as e:
            # raise
            # if current_app.config.get("DEBUG_MODDE"):
            # raise
            # logging.error(e)
            print(e, flush=True)
            response = HttpResponse(
                "Server Issue",
                status=500,
                content_type="text/plain",
            )
            return response

    wrapp_this_function.__name__ = func.__name__
    return wrapp_this_function
