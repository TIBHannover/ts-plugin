from django.views.decorators.http import require_http_methods
import requests
from user_service.libs.decorators import error_handler_decorator
from user_service.libs.utils import create_json_response
from django.http import Http404
from django.conf import settings
from user_service.middlewares.request import get_access_token_for_stats


@require_http_methods(["GET"])
def ping(request):
    return create_json_response({"response": "Pong"})


@error_handler_decorator
@require_http_methods(["GET"])
def harvest_datasets_terms_links(request):
    # if settings.STATS_API_TOKEN != get_access_token_for_stats():
    # raise Http404("not found")
    base_url = settings.NFDI4CHEM_SEARCH_SERVICE_ENDPOINT
    dataset_list_url = "{}/package_list".format(base_url)
    resp = requests.get(dataset_list_url)
    dataset_list = resp.json()
    dataset_list = dataset_list["result"]
    sample_dataset_title = dataset_list[0]
    fetch_dataset_url = "{}/package_show?id={}".format(base_url, sample_dataset_title)
    resp = requests.get(fetch_dataset_url)
    sample_dataset = resp.json()["result"]
    measurements = sample_dataset.get("variableMeasured")
    curies = []
    if measurements:
        for m in measurements:
            curies.append(m.get("variableMeasured_propertyID"))
    return create_json_response({"response": curies})
