import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from notification.github_updates import github_window_start, ontology_github_updates
from ontology_follow.models import OntologyFollowModel
from user.models import EmailLog, UserModel
from user_service.libs.email import Email


logger = logging.getLogger(__name__)


def digest_window_end(now):
    local = now.astimezone(ZoneInfo("Europe/Berlin"))
    end = local.replace(hour=7, minute=0, second=0, microsecond=0)
    if local < end:
        end -= timedelta(days=1)
    return end.astimezone(ZoneInfo("UTC"))


def digest_section(ontology_id, metadata, updates):
    if not updates["issues"] and not updates["commits"]:
        return ""
    lines = [f'{metadata["title"]} ({ontology_id})', f'https://github.com/{metadata["repository"]}']
    for key, label in (("issues", "New issues"), ("commits", f'New commits on {updates.get("branch", "main/master")}')):
        if updates[key]:
            lines.append(f"{label} ({len(updates[key])}):")
            lines.extend(f'- {item["title"]}\n  {item["url"]}' for item in updates[key])
    return "\n".join(lines)


@shared_task(bind=True, max_retries=12)
def send_github_digests(self, window_end=None):
    end = datetime.fromisoformat(window_end) if window_end else digest_window_end(timezone.now())
    follows = OntologyFollowModel.objects.filter(
        notify_github=True, user__is_active=True, user__is_blocked=False,
    ).exclude(user__email="")
    sections = {}
    retry_needed = False
    for ontology_id in follows.values_list("ontology_id", flat=True).distinct():
        try:
            metadata, updates = ontology_github_updates(ontology_id, end)
            sections[ontology_id] = digest_section(ontology_id, metadata, updates)
        except Exception:
            retry_needed = True
            logger.exception("Could not fetch GitHub updates for %s", ontology_id)
    for user_id in follows.values_list("user_id", flat=True).distinct():
        with transaction.atomic():
            user = UserModel.objects.select_for_update().get(pk=user_id)
            if not user.is_active or user.is_blocked or not user.email:
                continue
            ontology_ids = list(user.ontology_follows.filter(notify_github=True).order_by("ontology_id").values_list("ontology_id", flat=True))
            if any(oid not in sections for oid in ontology_ids):
                retry_needed = True
                continue
            included = [oid for oid in ontology_ids if sections.get(oid)]
            reference = f"github:{user.pk}:{end.isoformat()}"
            if not included or EmailLog.objects.filter(notification_type="ontology_github", reference=reference).exists():
                continue
            body = (
                f"GitHub updates from {github_window_start(end).isoformat()} to {end.isoformat()}.\n\n"
                + "\n\n".join(sections[oid] for oid in included)
            )
            Email(
                f'GitHub updates: {", ".join(included)}', body, client_ts=user.client_ts,
            ).send([user.email], notification_type="ontology_github", reference=reference)
    if retry_needed:
        raise self.retry(
            kwargs={"window_end": end.isoformat()}, countdown=600,
            exc=RuntimeError("Some ontology updates could not be fetched; affected digests deferred"),
        )
