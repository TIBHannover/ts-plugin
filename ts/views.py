from typing import DefaultDict
from django.views.decorators.http import require_http_methods
from user_service.libs.utils import create_json_response
from ts.models import TermDatasetLinkModel, HarvestFailureModel


@require_http_methods(["GET"])
def ping(request):
    return create_json_response({"response": "Pong"})


@require_http_methods(["GET"])
def get(request):
    curie = request.GET.get("curie")
    ontology_id = request.GET.get("ontology_id")
    repo_name = request.GET.get("repo_name")
    page = request.GET.get("page", 1)
    page_size = request.GET.get("size", 20)
    groupBy = request.GET.get("groupBy", "dataset")
    if curie:
        curies = [curie]
        if "_" in curie:
            curies.append(":".join(curie.split("_")))
        elif ":" in curie:
            curies.append("_".join(curie.split(":")))
    links = TermDatasetLinkModel.objects.filter(
        **({"curie__in": curies} if curie else {}),
        **({"ontology_id": ontology_id.lower()} if ontology_id else {}),
        **({"repo_name": repo_name} if repo_name else {}),
    )
    page = int(page)
    page_size = int(page_size)
    page = page if page > 0 else 1
    page_size = page_size if page_size > 0 else 20
    groupBy = groupBy.lower()
    groupBy = groupBy if groupBy in ["dataset", "term"] else "dataset"
    if groupBy == "dataset":
        q = links.values_list("dataset_title", flat=True).distinct()
        total = q.count()
        paged_titles = list(q[(page - 1) * page_size : page * page_size])
        rows = links.filter(dataset_title__in=paged_titles)
        result = DefaultDict(list)
        for row in rows:
            result[row.dataset_title].append(row.to_dict())
        return create_json_response(
            {
                "links": result,
                "total": total,
                "page": page,
                "size": page_size,
            }
        )

    # groupBy == "term"
    q = links.values_list("curie", flat=True).distinct()
    total = q.count()
    paged_curies = list(q[(page - 1) * page_size : page * page_size])
    rows = links.filter(curie__in=paged_curies)
    result = DefaultDict(list)
    for row in rows:
        result[row.curie].append(row.to_dict())
    return create_json_response(
        {
            "links": result,
            "total": total,
            "page": page,
            "size": page_size,
        }
    )


@require_http_methods(["GET"])
def get_repos_list(request):
    curie = request.GET.get("curie")
    ontology_id = request.GET.get("ontology_id")
    repo_name = request.GET.get("repo_name")
    links = TermDatasetLinkModel.objects.filter(
        **({"curie": curie} if curie else {}),
        **({"ontology_id": ontology_id.lower()} if ontology_id else {}),
        **({"repo_name": repo_name} if repo_name else {}),
    )
    repos = links.values_list("repo_name", flat=True).distinct()
    repos = [r for r in repos]
    return create_json_response({"repositories": repos})


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


@require_http_methods(["GET"])
def get_failed_harvests(request):
    failed_harvests = HarvestFailureModel.objects.all()
    return create_json_response(
        {"failed_harvests": [f.to_dict() for f in failed_harvests]}
    )
