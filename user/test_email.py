from smtplib import SMTPDataError, SMTPRecipientsRefused, SMTPServerDisconnected
from unittest.mock import call, patch

from celery.exceptions import Retry
from django.core import mail
from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from user.models import EmailLog, RoleModel, UserModel
from user.tasks import send_notification_email
from user_service.libs.email import Email


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="notifications@example.org",
)
class EmailTests(TestCase):
    def setUp(self):
        send_notification_email.push_request(retries=0)
        self.addCleanup(send_notification_email.pop_request)
        self.email = Email("Notification test", "Private message body", client_ts="general")

    def make_log(self, **kwargs):
        return EmailLog.objects.create(
            subject=self.email.subject,
            sender=self.email.sender_email,
            recipient="recipient@example.org",
            **kwargs,
        )

    @patch("user_service.libs.email.send_notification_email.delay")
    def test_generic_notification_logs_unique_recipients_and_queues_after_commit(self, delay):
        with self.captureOnCommitCallbacks(execute=True):
            logs = self.email.send(
                ["first@example.org", "second@example.org", "first@example.org"],
                notification_type="reminder",
                reference="collection:42",
            )
            delay.assert_not_called()
            self.assertEqual(EmailLog.objects.count(), 2)
        self.assertEqual(
            delay.call_args_list,
            [call(log.pk, self.email.body) for log in logs],
        )
        for log in logs:
            self.assertEqual(log.notification_type, "reminder")
            self.assertEqual(log.reference, "collection:42")
            self.assertEqual(log.client_ts, "general")
            self.assertEqual(log.sender, "notifications@example.org")
            self.assertEqual(log.subject, self.email.subject)
            self.assertEqual(log.status, EmailLog.Status.QUEUED)
            self.assertEqual(log.attempts, 0)
            self.assertIsNone(log.submitted_at)
            self.assertIsNotNone(log.created_at)
        self.assertNotIn("body", EmailLog.objects.values().first())

    @patch("user_service.libs.email.send_notification_email.delay")
    def test_rollback_removes_log_without_queueing(self, delay):
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(ValueError), transaction.atomic():
                self.email.send(["recipient@example.org"])
                raise ValueError("Rollback notification")
        self.assertFalse(EmailLog.objects.exists())
        delay.assert_not_called()

    @patch("user_service.libs.email.send_notification_email.delay")
    def test_no_recipients_creates_no_logs_or_tasks(self, delay):
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.email.send([]), [])
        self.assertFalse(EmailLog.objects.exists())
        delay.assert_not_called()

    @patch("user_service.libs.email.send_notification_email.delay", side_effect=OSError("Broker unavailable"))
    def test_broker_failure_is_recorded(self, delay):
        with self.assertLogs("user_service.libs.email", level="ERROR"):
            with self.captureOnCommitCallbacks(execute=True):
                log = self.email.send(["recipient@example.org"])[0]
        log.refresh_from_db()
        self.assertEqual(log.status, EmailLog.Status.FAILED)
        self.assertEqual(log.attempts, 0)
        self.assertEqual(log.last_error, "Broker unavailable")
        self.assertIsNone(log.submitted_at)

    def test_report_only_notifies_admins_with_email_in_the_same_service(self):
        user = UserModel.objects.create(username="admin", client_ts="general", created_at=timezone.now())
        for client_ts, role, target, address in [
            ("general", "admin", "system", "admin@example.org"),
            ("other", "admin", "system", "other@example.org"),
            ("general", "viewer", "system", "viewer@example.org"),
            ("general", "admin", "collection", "collection@example.org"),
            ("general", "admin", "system", ""),
            ("general", "admin", "system", None),
        ]:
            RoleModel.objects.create(
                user=user, client_ts=client_ts, role=role,
                target_object_type=target, target_object_id="",
                role_holder_email=address, created_at=timezone.now(),
            )
        with patch("user_service.libs.email.send_notification_email.delay"):
            with self.captureOnCommitCallbacks(execute=True):
                self.email.report_content_to_admins(reference="report:42")
        log = EmailLog.objects.get()
        self.assertEqual(log.recipient, "admin@example.org")
        self.assertEqual(log.notification_type, "content_report")
        self.assertEqual(log.reference, "report:42")

    def test_development_backend_captures_message_and_records_attempt(self):
        log = self.make_log()
        send_notification_email.run(log.pk, self.email.body)
        log.refresh_from_db()
        self.assertEqual(log.status, EmailLog.Status.CAPTURED)
        self.assertEqual(log.attempts, 1)
        self.assertIsNotNone(log.submitted_at)
        self.assertEqual(log.last_error, "")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [log.recipient])
        self.assertEqual(mail.outbox[0].body, self.email.body)
        self.assertEqual(mail.outbox[0].from_email, log.sender)
        self.assertEqual(mail.outbox[0].subject, log.subject)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend")
    @patch("django.core.mail.backends.smtp.smtplib.SMTP")
    def test_smtp_acceptance_records_submitted_not_delivered(self, smtp):
        smtp.return_value.sendmail.return_value = {}
        log = self.make_log()
        send_notification_email.run(log.pk, self.email.body)
        log.refresh_from_db()
        self.assertEqual(log.status, EmailLog.Status.SUBMITTED)
        self.assertEqual(log.attempts, 1)
        self.assertIsNotNone(log.submitted_at)
        self.assertEqual(smtp.return_value.sendmail.call_args.args[:2], (log.sender, [log.recipient]))

    @patch("user.tasks.send_mail")
    def test_completed_notifications_are_not_submitted_again(self, send_mail):
        for status in (EmailLog.Status.CAPTURED, EmailLog.Status.SUBMITTED):
            with self.subTest(status=status):
                log = self.make_log(status=status, attempts=1)
                send_notification_email.run(log.pk, self.email.body)
                log.refresh_from_db()
                self.assertEqual(log.attempts, 1)
        send_mail.assert_not_called()

    def test_temporary_failures_are_queued_for_retry(self):
        for error in (
            OSError("Connection refused"),
            SMTPServerDisconnected("Disconnected"),
            SMTPDataError(451, b"Try later"),
            SMTPRecipientsRefused({"recipient@example.org": (450, b"Mailbox busy")}),
        ):
            with self.subTest(error=error):
                log = self.make_log()
                with patch("user.tasks.send_mail", side_effect=error), \
                     patch.object(send_notification_email, "retry", side_effect=Retry) as retry, \
                     self.assertLogs("user.tasks", level="ERROR"), self.assertRaises(Retry):
                    send_notification_email.run(log.pk, self.email.body)
                log.refresh_from_db()
                self.assertEqual(log.status, EmailLog.Status.QUEUED)
                self.assertEqual(log.attempts, 1)
                self.assertEqual(log.last_error, str(error))
                self.assertIsNone(log.submitted_at)
                retry.assert_called_once_with(exc=error, countdown=30)

    def test_permanent_failures_are_not_retried(self):
        for error in (
            SMTPDataError(550, b"Rejected"),
            SMTPRecipientsRefused({"recipient@example.org": (550, b"Unknown recipient")}),
            ValueError("Invalid email header"),
        ):
            with self.subTest(error=error):
                log = self.make_log()
                with patch("user.tasks.send_mail", side_effect=error), \
                     patch.object(send_notification_email, "retry") as retry, \
                     self.assertLogs("user.tasks", level="ERROR"), self.assertRaises(type(error)):
                    send_notification_email.run(log.pk, self.email.body)
                log.refresh_from_db()
                self.assertEqual(log.status, EmailLog.Status.FAILED)
                self.assertEqual(log.last_error, str(error))
                self.assertEqual(log.attempts, 1)
                self.assertIsNone(log.submitted_at)
                retry.assert_not_called()

    def test_exhausted_retries_record_final_failure(self):
        send_notification_email.request.retries = send_notification_email.max_retries
        log = self.make_log(attempts=5)
        with patch("user.tasks.send_mail", side_effect=OSError("Still unavailable")), \
             patch.object(send_notification_email, "retry") as retry, \
             self.assertLogs("user.tasks", level="ERROR"), self.assertRaises(OSError):
            send_notification_email.run(log.pk, self.email.body)
        log.refresh_from_db()
        self.assertEqual(log.status, EmailLog.Status.FAILED)
        self.assertEqual(log.attempts, 6)
        self.assertEqual(log.last_error, "Still unavailable")
        retry.assert_not_called()

    def test_successful_retry_clears_error_and_counts_both_attempts(self):
        log = self.make_log()
        with patch("user.tasks.send_mail", side_effect=OSError("Temporary failure")), \
             patch.object(send_notification_email, "retry", side_effect=Retry), \
             self.assertLogs("user.tasks", level="ERROR"), self.assertRaises(Retry):
            send_notification_email.run(log.pk, self.email.body)
        send_notification_email.request.retries = 1
        send_notification_email.run(log.pk, self.email.body)
        log.refresh_from_db()
        self.assertEqual(log.status, EmailLog.Status.CAPTURED)
        self.assertEqual(log.attempts, 2)
        self.assertEqual(log.last_error, "")
        self.assertIsNotNone(log.submitted_at)
        self.assertEqual(len(mail.outbox), 1)

    @patch("user.tasks.send_mail", return_value=0)
    def test_backend_not_accepting_message_is_retried_without_success_status(self, send_mail):
        log = self.make_log()
        with patch.object(send_notification_email, "retry", side_effect=Retry) as retry, \
             self.assertLogs("user.tasks", level="ERROR"), self.assertRaises(Retry):
            send_notification_email.run(log.pk, self.email.body)
        log.refresh_from_db()
        self.assertEqual(log.status, EmailLog.Status.QUEUED)
        self.assertEqual(log.attempts, 1)
        self.assertEqual(log.last_error, "Email backend did not accept the message")
        self.assertIsNone(log.submitted_at)
        retry.assert_called_once()

    def test_recipient_failure_does_not_prevent_other_recipient_delivery(self):
        with patch("user_service.libs.email.send_notification_email.delay"):
            with self.captureOnCommitCallbacks(execute=True):
                failed, successful = self.email.send(["bad@example.org", "good@example.org"])
        with patch("user.tasks.send_mail", side_effect=SMTPDataError(550, b"Rejected")), \
             self.assertLogs("user.tasks", level="ERROR"), self.assertRaises(SMTPDataError):
            send_notification_email.run(failed.pk, self.email.body)
        send_notification_email.run(successful.pk, self.email.body)
        failed.refresh_from_db()
        successful.refresh_from_db()
        self.assertEqual(failed.status, EmailLog.Status.FAILED)
        self.assertEqual(successful.status, EmailLog.Status.CAPTURED)
        self.assertEqual(mail.outbox[0].to, ["good@example.org"])
