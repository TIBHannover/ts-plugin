from celery import shared_task, group
import requests
from django.conf import settings
from ts.models import TermDatasetLinkModel
from datetime import datetime as _time


@shared_task
def fetch_all_datasets():
    base_url = settings.NFDI4CHEM_SEARCH_SERVICE_ENDPOINT
    dataset_list_url = "{}/package_list".format(base_url)
    resp = requests.get(dataset_list_url)
    dataset_list = resp.json()
    dataset_list = dataset_list["result"]
    dataset_list = dataset_list[:10000]
    chunk_size = 1000
    tasks = [
        fetch_dataset_batch.s(dataset_list[i : i + chunk_size])
        for i in range(0, len(dataset_list), chunk_size)
    ]
    group(tasks).apply_async()


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=5,
)
def fetch_dataset_batch(dataset_titles: list[str]):
    session = requests.Session()
    result = {}
    for dataset_title in dataset_titles:
        result[dataset_title] = fetch_dataset(dataset_title, session)

    for dataset_title, curies in result.items():
        for curie in curies:
            curie = curie.strip()
            if ":" in curie:
                onto_id = curie.split(":")[0]
            elif "_" in curie:
                onto_id = curie.split("_")[0]
            else:
                onto_id = "unknown"
            term_dataset_link = TermDatasetLinkModel(
                created_at=_time.now(),
                curie=curie,
                ontology_id=onto_id,
                dataset_title=dataset_title,
            )
            term_dataset_link.save()
    return result


def fetch_dataset(dataset_title: str, session: requests.Session):
    try:
        fetch_dataset_url = "{}/package_show?id={}".format(
            settings.NFDI4CHEM_SEARCH_SERVICE_ENDPOINT, dataset_title
        )
        resp = session.get(fetch_dataset_url)
        if resp.status_code != 200:
            raise Exception(
                "Error fetching dataset({}): {}".format(dataset_title, resp.text)
            )
        sample_dataset = resp.json()["result"]
        measurements = sample_dataset.get("variableMeasured")
        curies = []
        if measurements:
            for m in measurements:
                curies.append(m.get("variableMeasured_propertyID"))
        return curies
    except Exception as e:
        print(e)
        return []
