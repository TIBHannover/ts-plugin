from concurrent.futures import ThreadPoolExecutor
from smtplib import SMTPDataError, SMTPRecipientsRefused, SMTPServerDisconnected
from threading import Event
from unittest.mock import ANY, call, patch

from celery.exceptions import Retry
from django.core import mail
from django.db import close_old_connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.utils import timezone

from notification.models import NotificationLog
from ontology_follow.models import OntologyFollowModel
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
            [call(log.pk, ANY, ANY) for log in logs],
        )
        for queued in delay.call_args_list:
            self.assertIn(self.email.body, queued.args[1])
            self.assertIn("About the Terminology Service", queued.args[2])
            self.assertIn("site_logo.webp", queued.args[2])
            self.assertNotIn("FOR SYSTEM ADMINS", queued.args[1])
            self.assertNotIn("FOR SYSTEM ADMINS", queued.args[2])
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
        self.assertFalse(NotificationLog.objects.exists())
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
        audit = NotificationLog.objects.get()
        self.assertEqual(audit.recipient, log.recipient)
        self.assertFalse(audit.success)

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
        with patch("user_service.libs.email.send_notification_email.delay") as delay:
            with self.captureOnCommitCallbacks(execute=True):
                self.email.report_content_to_admins(reference="report:42")
        log = EmailLog.objects.get()
        self.assertEqual(log.recipient, "admin@example.org")
        self.assertEqual(log.notification_type, "content_report")
        self.assertEqual(log.reference, "report:42")
        self.assertIn("FOR SYSTEM ADMINS", delay.call_args.args[1])
        self.assertIn("FOR SYSTEM ADMINS", delay.call_args.args[2])
        self.assertIn("background:#b91c1c", delay.call_args.args[2])

    @patch("user_service.libs.email.send_notification_email.delay")
    def test_shared_footer_uses_only_the_current_clients_frontend_base(self, delay):
        for client_ts in ("general", "nfdi4chem"):
            for base in ("https://example.org/ts", "https://example.org/ts/"):
                with self.subTest(client_ts=client_ts, base=base), override_settings(**{
                    f"{client_ts.upper()}_FRONTEND_REDIRECT_URL": base,
                    f"{'NFDI4CHEM' if client_ts == 'general' else 'GENERAL'}_FRONTEND_REDIRECT_URL": "https://other-client.example/ts/",
                }):
                    with self.captureOnCommitCallbacks(execute=True):
                        Email("Profile confirmation", "Address added", client_ts=client_ts).send(["user@example.org"])
                    for content in delay.call_args.args[1:]:
                        for path in ("contact", "docs", "TermsOfUse"):
                            self.assertIn(f"https://example.org/ts/{path}", content)
                        self.assertNotIn("FOR SYSTEM ADMINS", content)
                        self.assertNotIn("other-client.example", content)

    @override_settings(GENERAL_FRONTEND_REDIRECT_URL=None)
    @patch("user_service.libs.email.send_notification_email.delay")
    def test_missing_frontend_base_omits_footer_links_but_keeps_shared_layout(self, delay):
        with self.captureOnCommitCallbacks(execute=True):
            self.email.send(["user@example.org"])
        for content in delay.call_args.args[1:]:
            self.assertIn("About the Terminology Service", content)
            self.assertNotIn("TermsOfUse", content)
        self.assertIn("site_logo.webp", delay.call_args.args[2])

    @patch("user_service.libs.email.send_notification_email.delay")
    def test_shared_html_escapes_subject_and_body_and_preserves_links(self, delay):
        with self.captureOnCommitCallbacks(execute=True):
            Email("<script>subject</script>", '<img src=x onerror="alert(1)">\nhttps://example.org/note').send(["user@example.org"])
        html = delay.call_args.args[2]
        self.assertNotIn("<script>", html)
        self.assertNotIn("<img src=x", html)
        self.assertIn("&lt;script&gt;subject&lt;/script&gt;", html)
        self.assertIn("&lt;img", html)
        self.assertIn('href="https://example.org/note"', html)

    @patch("user_service.libs.email.send_notification_email.delay")
    def test_queued_shared_html_reaches_email_backend_as_alternative(self, delay):
        with self.captureOnCommitCallbacks(execute=True):
            self.email.send(["user@example.org"])
        send_notification_email.run(*delay.call_args.args)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.body, delay.call_args.args[1])
        self.assertEqual(message.alternatives[0][0], delay.call_args.args[2])
        self.assertEqual(message.alternatives[0][1], "text/html")

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
        self.assertFalse(NotificationLog.objects.get().success)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend")
    @patch("django.core.mail.backends.smtp.smtplib.SMTP")
    def test_smtp_acceptance_records_submitted_not_delivered(self, smtp):
        smtp.return_value.sendmail.return_value = {}
        log = self.make_log(notification_type="reminder", reference="collection:42")
        before = timezone.now()
        send_notification_email.run(log.pk, self.email.body)
        log.refresh_from_db()
        self.assertEqual(log.status, EmailLog.Status.SUBMITTED)
        self.assertEqual(log.attempts, 1)
        self.assertIsNotNone(log.submitted_at)
        self.assertEqual(smtp.return_value.sendmail.call_args.args[:2], (log.sender, [log.recipient]))
        audit = NotificationLog.objects.get()
        self.assertEqual(audit.trigger, "reminder: collection:42")
        self.assertEqual(audit.recipient, log.recipient)
        self.assertTrue(audit.success)
        self.assertLessEqual(before, audit.created_at)
        self.assertLessEqual(audit.created_at, timezone.now())
        self.assertEqual(set(NotificationLog.objects.values().get()), {
            "id", "trigger", "recipient", "success", "created_at",
        })

    @patch("user.tasks.send_mail")
    def test_completed_notifications_are_not_submitted_again(self, send_mail):
        for status in (EmailLog.Status.CAPTURED, EmailLog.Status.SUBMITTED):
            with self.subTest(status=status):
                log = self.make_log(status=status, attempts=1)
                send_notification_email.run(log.pk, self.email.body)
                log.refresh_from_db()
                self.assertEqual(log.attempts, 1)
        send_mail.assert_not_called()
        self.assertFalse(NotificationLog.objects.exists())

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
                self.assertFalse(NotificationLog.objects.latest("pk").success)

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
                self.assertFalse(NotificationLog.objects.latest("pk").success)

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
        self.assertEqual(NotificationLog.objects.count(), 2)

    def test_audit_database_failure_does_not_affect_sending_or_retry(self):
        create_audit = NotificationLog.objects.create

        def invalid_audit(**kwargs):
            return create_audit(**{**kwargs, "recipient": None})

        with patch.object(NotificationLog.objects, "create", side_effect=invalid_audit), \
             self.assertLogs("notification.models", level="ERROR"):
            log = self.make_log()
            send_notification_email.run(log.pk, self.email.body)
            log.refresh_from_db()
            self.assertEqual(log.status, EmailLog.Status.CAPTURED)
            self.assertEqual(len(mail.outbox), 1)

            log = self.make_log()
            error = OSError("Temporary failure")
            with patch("user.tasks.send_mail", side_effect=error), \
                 patch.object(send_notification_email, "retry", side_effect=Retry) as retry, \
                 self.assertLogs("user.tasks", level="ERROR"), self.assertRaises(Retry):
                send_notification_email.run(log.pk, self.email.body)
            retry.assert_called_once_with(exc=error, countdown=30)
            log.refresh_from_db()
            self.assertEqual(log.status, EmailLog.Status.QUEUED)
            self.assertEqual(log.last_error, str(error))
        self.assertFalse(NotificationLog.objects.exists())

    def test_audit_database_failure_does_not_interrupt_broker_failure_handling(self):
        create_audit = NotificationLog.objects.create

        def invalid_audit(**kwargs):
            return create_audit(**{**kwargs, "recipient": None})

        with patch.object(NotificationLog.objects, "create", side_effect=invalid_audit), \
             patch("user_service.libs.email.send_notification_email.delay", side_effect=OSError("Broker unavailable")), \
             self.assertLogs("notification.models", level="ERROR"), \
             self.assertLogs("user_service.libs.email", level="ERROR"):
            with self.captureOnCommitCallbacks(execute=True):
                logs = self.email.send(["first@example.org", "second@example.org"])
        for log in logs:
            log.refresh_from_db()
            self.assertEqual(log.status, EmailLog.Status.FAILED)
            self.assertEqual(log.last_error, "Broker unavailable")
        self.assertFalse(NotificationLog.objects.exists())

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

    @patch("user.tasks.send_mail")
    def test_ontology_retry_rechecks_recipient_and_subscription(self, send_mail):
        user = UserModel.objects.create(
            username="follower", created_at=timezone.now(), client_ts="general",
            email="recipient@example.org", email_verified=True,
        )
        for change in ("unfollow", "disable", "unverified", "email_changed", "blocked", "inactive"):
            with self.subTest(change=change):
                UserModel.objects.filter(pk=user.pk).update(
                    email="recipient@example.org", email_verified=True, is_active=True, is_blocked=False,
                )
                follow, _ = OntologyFollowModel.objects.update_or_create(
                    user=user, ontology_id="vibso", defaults={"notify_note": True},
                )
                log = self.make_log(notification_type="ontology_note", client_ts="general",
                                    recipient_user=user, ontology_ids=["vibso"])
                error = OSError("Temporary failure")
                send_mail.side_effect = error
                with patch.object(send_notification_email, "retry", side_effect=Retry), \
                     self.assertLogs("user.tasks", level="ERROR"), self.assertRaises(Retry):
                    send_notification_email.run(log.pk, self.email.body)
                if change == "unfollow":
                    follow.delete()
                elif change == "disable":
                    OntologyFollowModel.objects.filter(pk=follow.pk).update(notify_note=False)
                else:
                    fields = {"unverified": {"email_verified": False},
                              "email_changed": {"email": "new@example.org"},
                              "blocked": {"is_blocked": True}, "inactive": {"is_active": False}}
                    UserModel.objects.filter(pk=user.pk).update(**fields[change])
                send_mail.reset_mock()
                send_mail.side_effect = None
                send_notification_email.run(log.pk, self.email.body)
                send_mail.assert_not_called()
                log.refresh_from_db()
                self.assertEqual(log.status, EmailLog.Status.FAILED)
                self.assertEqual(log.attempts, 1)

    @patch("user.tasks.send_mail")
    def test_digest_with_partial_unfollow_is_suppressed(self, send_mail):
        user = UserModel.objects.create(
            username="digest", created_at=timezone.now(), client_ts="general",
            email="recipient@example.org", email_verified=True,
        )
        OntologyFollowModel.objects.create(user=user, ontology_id="vibso")
        log = self.make_log(notification_type="ontology_github", client_ts="general",
                            recipient_user=user, ontology_ids=["vibso", "bfo"])
        send_notification_email.run(log.pk, self.email.body)
        send_mail.assert_not_called()
        log.refresh_from_db()
        self.assertEqual(log.status, EmailLog.Status.FAILED)

    @patch("user.tasks.send_mail")
    def test_another_users_verified_shared_email_does_not_authorize_send(self, send_mail):
        user = UserModel.objects.create(
            username="unverified", created_at=timezone.now(), client_ts="general",
            email="recipient@example.org", email_verified=False,
        )
        other = UserModel.objects.create(
            username="verified", created_at=timezone.now(), client_ts="general",
            email=user.email, email_verified=True,
        )
        for follower in (user, other):
            OntologyFollowModel.objects.create(user=follower, ontology_id="vibso")
        for metadata in ({"recipient_user": user, "ontology_ids": ["vibso"]}, {}):
            with self.subTest(metadata=metadata):
                log = self.make_log(notification_type="ontology_note", client_ts="general", **metadata)
                send_notification_email.run(log.pk, self.email.body)
                log.refresh_from_db()
                self.assertEqual(log.status, EmailLog.Status.FAILED)
        send_mail.assert_not_called()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ConcurrentEmailTests(TransactionTestCase):
    available_apps = ["user", "notification"]

    @skipUnlessDBFeature("has_select_for_update")
    def test_concurrent_tasks_submit_a_notification_only_once(self):
        log = EmailLog.objects.create(subject="Concurrent", sender="sender@example.org",
                                      recipient="recipient@example.org")
        sending = Event()
        release = Event()
        second_started = Event()
        duplicate_send = Event()

        def send(*args, **kwargs):
            if sending.is_set():
                duplicate_send.set()
            sending.set()
            release.wait(5)
            return 1

        def run(second=False):
            close_old_connections()
            try:
                if second:
                    second_started.set()
                send_notification_email.run(log.pk, "Body")
            finally:
                close_old_connections()

        with patch("user.tasks.send_mail", side_effect=send) as submit, ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(run)
            try:
                self.assertTrue(sending.wait(5))
                second = pool.submit(run, True)
                self.assertTrue(second_started.wait(5))
                self.assertFalse(duplicate_send.wait(0.2))
            finally:
                release.set()
            first.result(timeout=5)
            second.result(timeout=5)
            submit.assert_called_once()
        self.assertEqual(NotificationLog.objects.count(), 1)
