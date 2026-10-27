import logging

from django.conf import settings
from django.db import transaction

from user.models import EmailLog, RoleModel
from user.tasks import send_notification_email


logger = logging.getLogger(__name__)


class Email:
    def __init__(self, subject, body, client_ts=""):
        self.subject = subject
        self.body = body
        self.sender_email = settings.DEFAULT_FROM_EMAIL
        self.client_ts = client_ts

    def send(self, recipients, notification_type="general", reference=""):
        logs = []
        for recipient in dict.fromkeys(recipients):
            email_log = EmailLog.objects.create(
                notification_type=notification_type,
                reference=reference,
                client_ts=self.client_ts,
                recipient=recipient,
                sender=self.sender_email,
                subject=self.subject,
            )
            logs.append(email_log)

            def enqueue(email_log_id=email_log.pk):
                try:
                    send_notification_email.delay(email_log_id, self.body)
                except Exception as exc:
                    EmailLog.objects.filter(pk=email_log_id).update(
                        status=EmailLog.Status.FAILED, last_error=str(exc)
                    )
                    logger.exception("Could not queue notification %s", email_log_id)

            transaction.on_commit(enqueue)
        return logs

    def report_content_to_admins(self, reference=""):
        self.send(
            RoleModel(client_ts=self.client_ts).get_system_admin_emails(),
            notification_type="content_report",
            reference=reference,
        )
        return True
