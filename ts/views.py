from django.views.decorators.http import require_http_methods
from user_service.libs.utils import create_json_response
from ts.models import TermDatasetLinkModel


@require_http_methods(["GET"])
def ping(request):
    return create_json_response({"response": "Pong"})


@require_http_methods(["GET"])
def get(request):
    curie = request.GET.get("curie")
    ontology_id = request.GET.get("ontology_id")
    repo_name = request.GET.get("repo_name")
    links = TermDatasetLinkModel.objects.filter(
        **({"curie": curie} if curie else {}),
        **({"ontology_id": ontology_id.lower()} if ontology_id else {}),
        **({"repo_name": repo_name} if repo_name else {}),
    )
    return create_json_response({"links": [l.to_dict() for l in links]})


@require_http_methods(["GET"])
def get_term_dataset_links(request):
    term_dataset_links = TermDatasetLinkModel.objects.all()
    return create_json_response(
        {"term_dataset_links": [t.to_dict() for t in term_dataset_links]}
    )


@require_http_methods(["GET"])
def delete_term_dataset_link(request):
    term_dataset_links = TermDatasetLinkModel.objects.all()
    term_dataset_links.delete()
    return create_json_response({"response": "Deleted all term dataset links"})
