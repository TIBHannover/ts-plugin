from urllib.parse import quote, urljoin

from django.conf import settings

from ontology_follow.models import OntologyFollowModel
from user_service.libs.email import Email


def ontology_update_link(instance, event, client_ts):
    redirect_url = getattr(settings, f"{client_ts.upper()}_FRONTEND_REDIRECT_URL", None)
    if not redirect_url or event not in ("note", "publication"):
        return ""
    page = "notes" if event == "note" else "publications"
    link = urljoin(
        redirect_url.rstrip("/") + "/",
        f"ontologies/{quote(instance.ontology_id.strip().lower(), safe='')}/{page}",
    )
    if event == "note":
        link += f"?noteId={instance.pk}"
    return link


def notify_ontology_followers(instance, event, user):
    if event == "note" and (not instance.active or instance.visibility == "me"):
        return
    ontology_id = instance.ontology_id.strip().lower()
    followers = OntologyFollowModel.objects.filter(
        ontology_id=ontology_id,
        user__client_ts=user.client_ts,
        user__is_active=True,
        user__is_blocked=False,
    ).exclude(user_id=user.pk).exclude(user__email="")
    labels = {"note": "note", "issue": "issue or term request", "publication": "publication"}
    link = ontology_update_link(instance, event, user.client_ts)
    Email(
        "Ontology update",
        f'A new {labels[event]} has been added to ontology "{ontology_id}".\n'
        f"Reference: {event}:{instance.pk}" + (f"\n{link}" if link else ""),
        client_ts=user.client_ts,
    ).send(
        followers.values_list("user__email", flat=True),
        notification_type=f"ontology_{event}",
        reference=f"{event}:{instance.pk}",
    )
