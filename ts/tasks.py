from celery import shared_task, group
import requests
from django.conf import settings


@shared_task
def fetch_all_datasets():
    base_url = settings.NFDI4CHEM_SEARCH_SERVICE_ENDPOINT
    dataset_list_url = "{}/package_list".format(base_url)
    resp = requests.get(dataset_list_url)
    dataset_list = resp.json()
    dataset_list = dataset_list["result"]
    chunk_size = 1000
    for i in range(0, len(dataset_list), chunk_size):
        dataset_titles = dataset_list[i : i + chunk_size]
        group(fetch_dataset.s(url) for url in dataset_titles).apply_async()


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def fetch_dataset(dataset_title: str):
    try:
        fetch_dataset_url = "{}/package_show?id={}".format(
            settings.NFDI4CHEM_SEARCH_SERVICE_ENDPOINT, dataset_title
        )
        resp = requests.get(fetch_dataset_url)
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
        print(curies)
        return curies
    except Exception as e:
        print(e)
        return []
