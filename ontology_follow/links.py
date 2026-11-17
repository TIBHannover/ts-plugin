from urllib.parse import urlencode, urljoin

from django.conf import settings
from django.core import signing


def unfollow_link(follow):
    base = (
        getattr(settings, f"{follow.user.client_ts.upper()}_EMAIL_ACTIVATION_BASE_URL", None)
        or getattr(settings, f"{follow.user.client_ts.upper()}_FRONTEND_REDIRECT_URL", None)
    )
    if not base:
        return ""
    token = signing.dumps({
        "follow_id": follow.pk, "ontology_id": follow.ontology_id,
    }, salt="ontology-unfollow")
    return urljoin(base.rstrip("/") + "/", "ontology/unfollow") + "?" + urlencode({
        "token": token, "ontology": follow.ontology_id,
    })
