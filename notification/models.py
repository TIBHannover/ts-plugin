import logging

from django.db import models, transaction


logger = logging.getLogger(__name__)


class NotificationLog(models.Model):
    trigger = models.TextField()
    recipient = models.EmailField()
    success = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notification_logs"
        ordering = ["-created_at"]

    @classmethod
    def record(cls, email_log, success):
        try:
            with transaction.atomic():
                cls.objects.create(
                    trigger=": ".join(filter(None, (email_log.notification_type, email_log.reference))),
                    recipient=email_log.recipient,
                    success=success,
                )
        except Exception:
            logger.exception("Could not log notification %s", email_log.pk)


class OntologyGitHubCache(models.Model):
    ontology_id = models.CharField(unique=True)
    metadata = models.JSONField(default=dict)
    metadata_expires_at = models.DateTimeField(null=True)
    updates = models.JSONField(default=dict)
    updates_expires_at = models.DateTimeField(null=True)
    window_end = models.DateTimeField(null=True)
