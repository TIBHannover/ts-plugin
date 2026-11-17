from urllib.parse import quote, urljoin

from django.conf import settings
from django.template.loader import render_to_string

from ontology_follow.models import OntologyFollowModel
from ontology_follow.links import unfollow_link
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


def note_email_content(instance, user, link):
    body = (
        f'A new note has been added to ontology "{instance.ontology_id.strip().lower()}".\n\n'
        f"Title: {instance.title}\nCreated by: {user.username}\n"
        + (f"View note: {link}\n" if link else "")
        + "\nYou received this email because you follow this ontology and have note notifications enabled."
    )
    return body, render_to_string("notification/new_note_email.html", {
        "note": instance, "username": user.username, "note_url": link,
    })


def notify_ontology_followers(instance, event, user):
    if event == "note" and (not instance.active or instance.visibility == "me"):
        return
    ontology_id = instance.ontology_id.strip().lower()
    followers = OntologyFollowModel.objects.filter(
        ontology_id=ontology_id,
        user__client_ts=user.client_ts,
        user__is_active=True,
        user__is_blocked=False,
        user__email_verified=True,
        **{f"notify_{event}": True},
    ).exclude(user_id=user.pk).exclude(user__email="")
    labels = {"note": "note", "issue": "issue or term request", "publication": "publication"}
    link = ontology_update_link(instance, event, user.client_ts)
    title = getattr(instance, {"note": "title", "issue": "issue_title", "publication": "citation"}[event], "")
    if event == "publication" and not title:
        title = instance.doi
    body = (
        f'A new {labels[event]} has been added to ontology "{ontology_id}".\n'
        + (f"\n{title}\n" if title else "")
        + (f"\n{link}" if link else "")
    )
    html_body = None
    if event == "note":
        body, html_body = note_email_content(instance, user, link)
    for follow in followers.select_related("user"):
        url = unfollow_link(follow)
        Email(
            f"Ontology update: {ontology_id}",
            body,
            client_ts=user.client_ts,
            html_body=html_body,
            unfollow_links=[(ontology_id, url)] if url else [],
        ).send(
            [follow.user.email],
            notification_type=f"ontology_{event}",
            reference=f"{event}:{instance.pk}",
        )
