from celery import shared_task, chord
import requests
from django.conf import settings
from ts.models import TermDatasetLinkModel
from datetime import datetime as _time
from ts.models import HarvestFailureModel


@shared_task
def fetch_all_datasets():
    base_url = settings.NFDI4CHEM_SEARCH_SERVICE_ENDPOINT
    dataset_list_url = "{}/package_list".format(base_url)
    resp = requests.get(dataset_list_url)
    HarvestFailureModel.objects.all().delete()
    if resp.status_code != 200:
        print("Error fetching dataset_list: code={}".format(resp.status_code))
        return
    dataset_list = resp.json()
    dataset_list = dataset_list["result"]
    # dataset_list = dataset_list[:20000]
    chunk_size = 1000
    tasks = [
        fetch_dataset_batch.s(dataset_list[i : i + chunk_size])
        for i in range(0, len(dataset_list), chunk_size)
    ]
    chord(tasks)(on_finish.s())


@shared_task
def fetch_all_failed_datasets():
    failed = HarvestFailureModel.objects.all()
    dataset_list = [f.dataset_title for f in failed]
    HarvestFailureModel.objects.all().delete()
    chunk_size = 1000
    tasks = [
        fetch_dataset_batch.s(dataset_list[i : i + chunk_size])
        for i in range(0, len(dataset_list), chunk_size)
    ]
    chord(tasks)(on_finish.s())


@shared_task
def on_finish(results):
    print("Finished fetching all datasets!")


@shared_task(rate_limit="60/m")
def fetch_dataset_batch(dataset_titles: list[str]):
    session = requests.Session()
    result = {}
    for dataset_title in dataset_titles:
        curies, terms_labels, repo_name, dataset_description = fetch_dataset_handler(
            dataset_title, session
        )
        if not curies:
            continue
        result[dataset_title] = {
            "curies": curies,
            "repo_name": repo_name,
            "terms_labels": terms_labels,
            "dataset_description": dataset_description,
        }

    for dataset_title, metadata in result.items():
        curies = metadata["curies"]
        repo_name = metadata["repo_name"]
        i = 0
        for curie in curies:
            curie = curie.strip()
            existing = TermDatasetLinkModel.objects.filter(
                curie=curie, dataset_title=dataset_title
            ).first()
            if existing:
                i += 1
                continue
            if ":" in curie:
                onto_id = curie.split(":")[0]
            elif "_" in curie:
                onto_id = curie.split("_")[0]
            else:
                onto_id = "unknown"
            term_dataset_link = TermDatasetLinkModel(
                created_at=_time.now(),
                curie=curie,
                ontology_id=onto_id.lower(),
                dataset_title=dataset_title,
                repo_name=repo_name,
                dataset_description=metadata["dataset_description"],
                term_label=metadata["terms_labels"][i],
            )
            term_dataset_link.save()
            i += 1
    print("Finished a batch.")


def fetch_dataset_handler(dataset_title: str, session: requests.Session):
    try:
        return fetch_dataset(dataset_title, session)
    except Exception:
        return [], [], "unknown", "unknown"


def fetch_dataset(dataset_title: str, session: requests.Session):
    try:
        fetch_dataset_url = "{}/package_show?id={}".format(
            settings.NFDI4CHEM_SEARCH_SERVICE_ENDPOINT, dataset_title
        )
        resp = session.get(fetch_dataset_url)
        harvest_failure = HarvestFailureModel()
        if resp.status_code != 200:
            harvest_failure.created_at = _time.now()
            harvest_failure.dataset_title = dataset_title
            harvest_failure.error_code = resp.status_code
            harvest_failure.save()
            return [], [], "unknown", "unknown"

        sample_dataset = resp.json()["result"]
        return extract_metadata_from_dataset(sample_dataset)
    except:
        harvest_failure.created_at = _time.now()
        harvest_failure.dataset_title = dataset_title
        harvest_failure.error_code = 500
        harvest_failure.save()
        return [], [], "unknown", "unknown"


def extract_metadata_from_dataset(dataset):
    measurements = dataset.get("variableMeasured")
    curies = []
    terms_labels = []
    if measurements:
        for m in measurements:
            curies.append(m.get("variableMeasured_propertyID"))
            terms_labels.append(m.get("variableMeasured_name"))
    repo_name = dataset.get("organization", {}).get("title")
    if not repo_name:
        repo_name = "unknown"
    return curies, terms_labels, repo_name, dataset.get("notes", "N/A")
