from django.http import JsonResponse


def create_json_response(response_dict):
    return JsonResponse({"_result": response_dict})
