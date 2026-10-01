from django.views.decorators.http import require_POST
from user_service.libs.decorators import authentication_required

from .workflows import start_term_request_workflow


@require_POST
@authentication_required
def start_agent(request):
    """Backward-compatible term-request entry point."""
    return start_term_request_workflow(request, include_workflow=False)


@require_POST
@authentication_required
def start_term_request(request):
    return start_term_request_workflow(request)
