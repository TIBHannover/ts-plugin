from celery import shared_task, chord
import requests
from django.conf import settings
from ts.models import TermDatasetLinkModel
from datetime import datetime as _time
import time


@shared_task
def fetch_all_datasets():
    base_url = settings.NFDI4CHEM_SEARCH_SERVICE_ENDPOINT
    dataset_list_url = "{}/package_list".format(base_url)
    resp = requests.get(dataset_list_url)
    if resp.status_code != 200:
        print("Error fetching dataset_list: code={}".format(resp.status_code))
        return
    dataset_list = resp.json()
    dataset_list = dataset_list["result"]
    dataset_list = dataset_list[:20000]
    chunk_size = 1000
    tasks = [
        fetch_dataset_batch.s(dataset_list[i : i + chunk_size])
        for i in range(0, len(dataset_list), chunk_size)
    ]
    chord(tasks)(on_finish.s())


@shared_task
def on_finish(results):
    print("Finished fetching all datasets!")


# @shared_task(
#     autoretry_for=(Exception,),
#     retry_backoff=True,
#     retry_backoff_max=120,
#     retry_jitter=True,
#     max_retries=5,
# )
@shared_task(rate_limit="60/m")
def fetch_dataset_batch(dataset_titles: list[str]):
    session = requests.Session()
    result = {}
    for dataset_title in dataset_titles:
        curies, repo_name = fetch_dataset_handler(dataset_title, session)
        if not curies:
            continue
        result[dataset_title] = {"curies": curies, "repo_name": repo_name}

    for dataset_title, metadata in result.items():
        curies = metadata["curies"]
        repo_name = metadata["repo_name"]
        for curie in curies:
            curie = curie.strip()
            existing = TermDatasetLinkModel.objects.filter(
                curie=curie, dataset_title=dataset_title
            ).first()
            if existing:
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
                ontology_id=onto_id,
                dataset_title=dataset_title,
                repo_name=repo_name,
            )
            term_dataset_link.save()
    print("Finished a batch.")


def fetch_dataset_handler(dataset_title: str, session: requests.Session):
    try:
        curies, repo_name = fetch_dataset(dataset_title, session)
        return curies, repo_name
    except Exception as e:
        print(e)
        return [], "unknown"


def fetch_dataset(dataset_title: str, session: requests.Session):
    try:
        fetch_dataset_url = "{}/package_show?id={}".format(
            settings.NFDI4CHEM_SEARCH_SERVICE_ENDPOINT, dataset_title
        )
        resp = session.get(fetch_dataset_url)
        if resp.status_code != 200:
            print(
                "Error fetching dataset({}): code={}".format(
                    dataset_title, resp.status_code
                )
            )
            print("calling again in 5 seconds")
            time.sleep(2)
            resp = session.get(fetch_dataset_url)
            if resp.status_code != 200:
                print(
                    "Error fetching dataset({}): code={}".format(
                        dataset_title, resp.status_code
                    )
                )
                print("Ignoring this dataset")
                return [], "unknown"

        sample_dataset = resp.json()["result"]
        return extract_metadata_from_dataset(sample_dataset)
    except:
        print("Error fetching dataset({}): Exception cought".format(dataset_title))
        print("calling again in 5 seconds")
        time.sleep(2)
        resp = session.get(fetch_dataset_url)
        if resp.status_code != 200:
            print(
                "Error fetching dataset({}): code={}".format(
                    dataset_title, resp.status_code
                )
            )
            print("Ignoring this dataset")
            return [], "unknown"
        sample_dataset = resp.json()["result"]
        return extract_metadata_from_dataset(sample_dataset)


def extract_metadata_from_dataset(dataset):
    measurements = dataset.get("variableMeasured")
    curies = []
    if measurements:
        for m in measurements:
            curies.append(m.get("variableMeasured_propertyID"))
    repo_name = dataset.get("organization", {}).get("title")
    if not repo_name:
        repo_name = "unknown"
    return curies, repo_name
