from functools import partial

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from github.models import GithubIssueRequestModel
from note.models import NoteModel
from notification.services import notify_ontology_followers
from pub_link.models import PubLinkModel


@receiver(post_save, sender=NoteModel)
@receiver(post_save, sender=GithubIssueRequestModel)
@receiver(post_save, sender=PubLinkModel)
def ontology_content_created(sender, instance, created, raw, **kwargs):
    if not created or raw:
        return
    if sender is GithubIssueRequestModel:
        event, user = "issue", instance.user
        if user.client_ts != instance.client_ts:
            return
    else:
        event = "note" if sender is NoteModel else "publication"
        user = instance.creator
    transaction.on_commit(
        partial(notify_ontology_followers, instance, event, user), robust=True
    )
