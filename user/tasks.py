from celery import shared_task
from django.core.mail import get_connection, send_mail
from django.core.mail.backends.smtp import EmailBackend as SMTPBackend
from django.db.models import F
from django.utils import timezone
import logging
from smtplib import (
    SMTPException,
    SMTPRecipientsRefused,
    SMTPResponseException,
    SMTPServerDisconnected,
)

from notification.models import NotificationLog
from user.models import EmailLog, OAuthLoginTransaction, UserModel


logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5)
def send_notification_email(self, email_log_id, body, html_body=None):
    email_log = EmailLog.objects.get(pk=email_log_id)
    if email_log.status in (EmailLog.Status.SUBMITTED, EmailLog.Status.CAPTURED):
        return
    if email_log.notification_type.startswith("ontology_") and not UserModel.objects.filter(
        email=email_log.recipient, client_ts=email_log.client_ts,
        email_verified=True, is_active=True, is_blocked=False,
    ).exists():
        EmailLog.objects.filter(pk=email_log_id).update(
            status=EmailLog.Status.FAILED, last_error="Recipient email is no longer verified or active",
        )
        NotificationLog.record(email_log, success=False)
        return
    EmailLog.objects.filter(pk=email_log_id).update(
        attempts=F("attempts") + 1, status=EmailLog.Status.QUEUED, last_error=""
    )
    try:
        connection = get_connection()
        if not send_mail(
            email_log.subject, body, email_log.sender, [email_log.recipient],
            fail_silently=False, connection=connection, html_message=html_body,
        ):
            raise SMTPException("Email backend did not accept the message")
    except Exception as exc:
        logger.exception("Notification %s submission failed", email_log_id)
        temporary = isinstance(exc, (OSError, SMTPServerDisconnected))
        if isinstance(exc, SMTPResponseException):
            temporary = 400 <= exc.smtp_code < 500
        elif isinstance(exc, SMTPRecipientsRefused):
            temporary = bool(exc.recipients) and all(
                400 <= code < 500 for code, _ in exc.recipients.values()
            )
        retry = temporary and self.request.retries < self.max_retries
        EmailLog.objects.filter(pk=email_log_id).update(
            status=EmailLog.Status.QUEUED if retry else EmailLog.Status.FAILED,
            last_error=str(exc),
        )
        NotificationLog.record(email_log, success=False)
        if retry:
            raise self.retry(exc=exc, countdown=min(30 * 2 ** self.request.retries, 600))
        raise
    EmailLog.objects.filter(pk=email_log_id).update(
        status=(
            EmailLog.Status.SUBMITTED if isinstance(connection, SMTPBackend)
            else EmailLog.Status.CAPTURED
        ),
        submitted_at=timezone.now(), last_error="",
    )
    NotificationLog.record(email_log, success=isinstance(connection, SMTPBackend))


@shared_task
def cleanup_expired_oauth_login_transactions():
    OAuthLoginTransaction.objects.filter(expires_at__lt=timezone.now()).delete()
