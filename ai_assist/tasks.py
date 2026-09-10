from celery import shared_task

from .ontology_harvester import harvest_ontologies
from .term_request_search.runner import (
    resume_term_request_search_agent,
    run_term_request_search_agent,
)


@shared_task
def harvest_ontologies_task():
    return harvest_ontologies()


@shared_task
def run_agent_task(run_id, input_text, workflow="term_request"):
    return run_term_request_search_agent(run_id, input_text, workflow)


@shared_task
def resume_agent_task(run_id):
    return resume_term_request_search_agent(run_id)
