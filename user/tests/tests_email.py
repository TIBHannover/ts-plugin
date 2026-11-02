import json
from unittest.mock import patch

from django.test import override_settings
from django.utils import timezone

from user.models import UserModel
from user_service.libs.test_config import BaseTest


@override_settings(DEBUG=False)
class UserEmailTests(BaseTest):
    url = "/user/email/"

    def setUp(self):
        login = patch("user.libs.github.GithubLib.login_valid", return_value=True)
        login.start()
        self.addCleanup(login.stop)

    def request(self, method, payload=None, headers=None):
        return getattr(self.client, method)(
            self.url,
            data={} if method == "get" else json.dumps(payload) if payload is not None else "",
            content_type="application/json",
            headers=headers or self.github_request_headers,
        )

    def test_email_lifecycle_and_public_serialization(self):
        self.assertEqual(self.request("get").json()["_result"], {"email": ""})
        for method, address in (("post", "first@example.org"), ("put", "second@example.org")):
            response = self.request(method, {"email": f" {address} "})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["_result"], {"email": address})
            self.gitHubUser.refresh_from_db()
            self.assertEqual(self.gitHubUser.email, address)
            self.assertEqual(self.request("get").json()["_result"], {"email": address})
            self.assertNotIn("email", self.gitHubUser.to_dict())
        for _ in range(2):
            response = self.request("delete")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["_result"], {"email": ""})
        self.gitHubUser.refresh_from_db()
        self.assertEqual(self.gitHubUser.email, "")

    def test_invalid_emails_preserve_existing_email(self):
        self.gitHubUser.email = "keep@example.org"
        self.gitHubUser.save()
        for payload in ({}, {"email": None}, {"email": 123}, {"email": ""},
                        {"email": "bad-address"}, {"email": "x" * 255 + "@example.org"}, []):
            for method in ("post", "put"):
                with self.subTest(payload=payload, method=method):
                    self.assertEqual(self.request(method, payload).status_code, 400)
        self.gitHubUser.refresh_from_db()
        self.assertEqual(self.gitHubUser.email, "keep@example.org")

    def test_malformed_json_is_rejected(self):
        response = self.client.put(self.url, data="{", content_type="application/json", headers=self.github_request_headers)
        self.assertEqual(response.status_code, 400)

    def test_email_belongs_to_current_user_and_client(self):
        other_client = UserModel.objects.create(
            username=self.gitHubUser.username, client_ts="nfdi4chem",
            auth_provider="github", created_at=timezone.now(), email="chem@example.org",
        )
        response = self.request("put", {"email": "general@example.org"})
        self.assertEqual(response.status_code, 200)
        other_client.refresh_from_db()
        self.assertEqual(other_client.email, "chem@example.org")
        headers = {**self.github_request_headers, "X-TS-Frontend-Id": "nfdi4chem"}
        self.assertEqual(self.request("get", headers=headers).json()["_result"], {"email": "chem@example.org"})
        self.assertEqual(self.request("delete", headers=headers).status_code, 200)
        self.gitHubUser.refresh_from_db()
        self.assertEqual(self.gitHubUser.email, "general@example.org")
        self.orcidUser.refresh_from_db()
        self.assertEqual(self.orcidUser.email, "")

    def test_all_email_operations_require_authentication(self):
        for method in ("get", "post", "put", "delete"):
            with self.subTest(method=method):
                self.assertEqual(self.request(method, {"email": "guest@example.org"}, self.guest_request_headers).status_code, 401)
        self.gitHubUser.refresh_from_db()
        self.assertEqual(self.gitHubUser.email, "")
