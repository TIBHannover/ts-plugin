from celery import shared_task
import json

from .redis_client import redis_client
from .transport import RUN_REDIS_KEY_STATE, run_redis_key
from .ontology_harvester import harvest_ontologies
@shared_task
def harvest_ontologies_task():
    return harvest_ontologies()


@shared_task
def run_agent_task(run_id, input_text, workflow="term_request", search_inputs=None):
    if workflow == "search":
        from .search_agent.runner import run_search_agent

        return run_search_agent(run_id, input_text)
    from .term_request_assist.runner import run_term_request_search_agent

    if search_inputs is None:
        return run_term_request_search_agent(run_id, input_text, workflow)
    return run_term_request_search_agent(run_id, input_text, workflow, search_inputs)


@shared_task
def resume_agent_task(run_id):
    state_json = redis_client.get(run_redis_key(run_id, RUN_REDIS_KEY_STATE))
    try:
        state = json.loads(state_json) if state_json else {}
    except (TypeError, json.JSONDecodeError):
        state = {}
    if state.get("workflow") == "search":
        from .search_agent.runner import resume_search_agent

        return resume_search_agent(run_id)
    from .term_request_assist.runner import resume_term_request_search_agent

    return resume_term_request_search_agent(run_id)
