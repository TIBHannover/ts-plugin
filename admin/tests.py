from unittest.mock import patch

from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from user.models import EmailLog, RoleModel, UserModel
from user_service.libs.test_helpers import TestHelper
from user_service.libs.utils import make_hash


@override_settings(DEBUG=False)
class TestSendTestEmail(TransactionTestCase):
    available_apps = ["user", "admin"]

    def setUp(self):
        self.url = "/admin/send_test_email/"
        self.user = UserModel.objects.create(
            username="github_test_admin",
            auth_provider="github",
            client_ts="general",
            created_at=timezone.now(),
        )
        self.headers = {
            "X-TS-Frontend-Id": "general",
            "X-TS-Auth-Provider": "github",
            "X-CSRF-Token": "test-csrf-token",
        }
        self.client.cookies["jwt"] = TestHelper.generate_jwt(
            {}, self.user.username, "provider-token", csrf_token="test-csrf-token"
        )
        self.provider_login = self.enterContext(
            patch("user.libs.auth.GithubLib.login_valid", return_value=True)
        )
        self.queue_email = self.enterContext(
            patch("user_service.libs.email.send_notification_email.delay")
        )

    def create_role(self, **overrides):
        return RoleModel.objects.create(
            **{
                "user": self.user,
                "created_at": timezone.now(),
                "target_object_id": "system",
                "target_object_type": "system",
                "role": "admin",
                "client_ts": "general",
                "role_holder_email": "admin@example.org",
                **overrides,
            }
        )

    def assert_no_email(self):
        self.assertFalse(EmailLog.objects.exists())
        self.queue_email.assert_not_called()

    def test_system_admin_queues_only_own_role_email(self):
        self.create_role(target_object_type="ontology", target_object_id="example")
        self.create_role()
        other_user = UserModel.objects.create(
            username="github_other_admin",
            auth_provider="github",
            client_ts="general",
            created_at=timezone.now(),
        )
        self.create_role(user=other_user, role_holder_email="other@example.org")

        response = self.client.post(
            self.url,
            {"recipient": "untrusted@example.org", "email": "untrusted@example.org"},
            content_type="application/json",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 202)
        email_log = EmailLog.objects.get()
        self.assertEqual(email_log.recipient, "admin@example.org")
        self.assertEqual(email_log.client_ts, "general")
        self.assertEqual(email_log.notification_type, "test_email")
        self.assertEqual(email_log.status, EmailLog.Status.QUEUED)
        self.assertEqual(
            response.json()["_result"],
            {"email_log_id": email_log.pk, "status": EmailLog.Status.QUEUED},
        )
        self.queue_email.assert_called_once_with(
            email_log.pk, "This is a test email from the TS Plugin service."
        )

    def test_anonymous_request_is_rejected(self):
        self.create_role()
        self.client.cookies.clear()

        response = self.client.post(self.url, headers=self.headers)

        self.assertEqual(response.status_code, 401)
        self.assert_no_email()

    def test_admin_without_csrf_token_is_rejected(self):
        self.create_role()
        del self.headers["X-CSRF-Token"]

        response = self.client.post(self.url, headers=self.headers)

        self.assertEqual(response.status_code, 401)
        self.assert_no_email()

    def test_invalid_provider_session_is_rejected(self):
        self.create_role()
        self.provider_login.return_value = False

        response = self.client.post(self.url, headers=self.headers)

        self.assertEqual(response.status_code, 401)
        self.assert_no_email()

    def test_user_without_admin_role_is_rejected(self):
        response = self.client.post(self.url, headers=self.headers)

        self.assertEqual(response.status_code, 403)
        self.assert_no_email()

    def test_non_system_roles_are_rejected(self):
        for overrides in (
            {"target_object_type": "ontology", "target_object_id": "example"},
            {"role": "viewer"},
            {"target_object_id": "other-system"},
        ):
            with self.subTest(overrides=overrides):
                role = self.create_role(**overrides)
                response = self.client.post(self.url, headers=self.headers)
                self.assertEqual(response.status_code, 403)
                self.assert_no_email()
                role.delete()

    def test_other_client_admin_role_is_rejected(self):
        self.create_role(client_ts="nfdi4chem")

        response = self.client.post(self.url, headers=self.headers)

        self.assertEqual(response.status_code, 403)
        self.assert_no_email()

    def test_other_client_user_with_same_username_does_not_grant_access(self):
        other_user = UserModel.objects.create(
            username=self.user.username,
            auth_provider="github",
            client_ts="nfdi4chem",
            created_at=timezone.now(),
        )
        self.create_role(user=other_user)

        response = self.client.post(self.url, headers=self.headers)

        self.assertEqual(response.status_code, 403)
        self.assert_no_email()

    def test_blocked_or_inactive_admin_is_rejected(self):
        self.create_role()
        for is_blocked, is_active in ((True, True), (False, False)):
            with self.subTest(is_blocked=is_blocked, is_active=is_active):
                UserModel.objects.filter(pk=self.user.pk).update(
                    is_blocked=is_blocked, is_active=is_active
                )
                response = self.client.post(self.url, headers=self.headers)
                self.assertIn(response.status_code, (401, 403))
                self.assert_no_email()

    def test_missing_role_email_is_rejected(self):
        for email in (None, ""):
            with self.subTest(email=email):
                role = self.create_role(role_holder_email=email)
                response = self.client.post(self.url, headers=self.headers)
                self.assertEqual(response.status_code, 400)
                self.assert_no_email()
                role.delete()

    def test_queue_failure_returns_service_unavailable_and_failed_log(self):
        self.create_role()
        self.queue_email.side_effect = ConnectionError("Broker unavailable")

        with self.assertLogs("user_service.libs.email", level="ERROR"):
            response = self.client.post(self.url, headers=self.headers)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["_result"], "Could not queue test email")
        email_log = EmailLog.objects.get()
        self.assertEqual(email_log.status, EmailLog.Status.FAILED)
        self.assertEqual(email_log.last_error, "Broker unavailable")
        self.queue_email.assert_called_once()

    def test_get_is_not_allowed(self):
        self.create_role()

        response = self.client.get(self.url, headers=self.headers)

        self.assertEqual(response.status_code, 405)
        self.assert_no_email()

    def test_non_admin_api_key_cannot_use_owners_admin_role(self):
        self.create_role()
        UserModel.objects.create(
            username="api_test_admin",
            auth_provider="apikey",
            client_ts="general",
            created_at=timezone.now(),
            api_key=make_hash("apk_general_test-email"),
            owner=self.user,
        )
        self.client.cookies.clear()

        response = self.client.post(
            self.url, headers={"Authorization": "apk_general_test-email"}
        )

        self.assertEqual(response.status_code, 403)
        self.assert_no_email()
