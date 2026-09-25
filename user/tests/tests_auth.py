from user_service.libs.test_config import BaseTest
from user_service.libs.test_helpers import TestHelper
from django.conf import settings
from django.test import override_settings
from django.utils import timezone
from jose import jwt
from user.models import MAX_API_KEY_OWNER_DEPTH, UserModel
from user_service.libs.utils import make_hash
import copy
import datetime
import json
import secrets
from unittest.mock import patch


class TestAuth(BaseTest):
    @classmethod
    def setUpTestData(self) -> None:
        super().setUpTestData()
        self.auth_url = "/user/close_endpoint/"
        self.keydata = {
            "name": "project_x",
            "title": "Test API Key",
            "description": "this is a test API Key",
            "expires_at": None,
        }

    def test_auth_cookie_should_success(self):
        headers = copy.copy(self.github_request_headers)
        response = self.client.get(self.auth_url, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("_result").get("response"), "closed")

    def test_auth_should_success_with_jwt_cookie(self):
        headers = copy.copy(self.github_request_headers)
        headers.pop("X-Auth-Token")
        self.client.cookies["jwt"] = self.github_user_jwt

        response = self.client.get(self.auth_url, headers=headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("_result").get("response"), "closed")

    def test_auth_with_jwt_cookie_should_still_require_csrf(self):
        headers = copy.copy(self.github_request_headers)
        headers.pop("X-Auth-Token")
        headers.pop("X-CSRF-Token")
        self.client.cookies["jwt"] = self.github_user_jwt

        response = self.client.get(self.auth_url, headers=headers)

        self.assertEqual(response.status_code, 401)
        self.assertIn("request is not valid", response.content.decode())

    def test_auth_with_jwt_cookie_should_fail_with_wrong_csrf(self):
        headers = copy.copy(self.github_request_headers)
        headers.pop("X-Auth-Token")
        headers["X-CSRF-Token"] = "wrong"
        self.client.cookies["jwt"] = self.github_user_jwt

        response = self.client.get(self.auth_url, headers=headers)

        self.assertEqual(response.status_code, 401)
        self.assertIn("request is not valid", response.content.decode())

    def test_auth_should_prefer_header_token_over_cookie(self):
        headers = copy.copy(self.orcid_request_headers)
        self.client.cookies["jwt"] = self.github_user_jwt

        response = self.client.get(self.auth_url, headers=headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("_result").get("response"), "closed")

    def test_auth_should_accept_legacy_header_jwt_with_signed_csrf(self):
        legacy_jwt = jwt.encode(
            {
                "exp": datetime.datetime.now(datetime.UTC)
                + datetime.timedelta(60 * 5),
                "ts_username": self.gitHubUser.username,
                "orcid_id": "",
                "token": self.github_access_token,
            },
            settings.SECRET_KEY,
            algorithm="HS256",
        )
        legacy_csrf = jwt.encode(
            {"csrf": "legacy-csrf"},
            settings.SECRET_KEY,
            algorithm="HS256",
        )
        headers = copy.copy(self.github_request_headers)
        headers["X-Auth-Token"] = legacy_jwt
        headers["X-CSRF-Token"] = legacy_csrf

        response = self.client.get(self.auth_url, headers=headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("_result").get("response"), "closed")

    def test_auth_should_fail_for_guest(self):
        # csrf token is missing
        headers = copy.copy(self.guest_request_headers)
        response = self.client.get(self.auth_url, headers=headers)
        self.assertEqual(response.status_code, 401)
        self.assertIn("request is not valid", response.content.decode())

    def test_auth_should_fail_with_csrf_but_wrong_token(self):
        headers = copy.copy(self.github_request_headers)
        headers["X-Auth-Token"] = "some_token"
        response = self.client.get(self.auth_url, headers=headers)
        self.assertEqual(response.status_code, 401)
        self.assertIn("request is not valid", response.content.decode())

    def test_auth_should_success_with_api_key(self):
        headers = copy.copy(self.github_request_headers)
        response = self.client.post(
            "/user/apikey/create/",
            headers=headers,
            data=json.dumps(self.keydata),
            content_type="application/json",
        )
        api_key = response.json().get("_result").get("token")

        # we empty these to make sure auth is done only with api key
        headers["X-CSRF-Token"] = ""
        headers["X-Auth-Token"] = ""
        headers["Authorization"] = api_key
        self.client.cookies["jwt"] = "invalid"
        response = self.client.get(self.auth_url, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("_result").get("response"), "closed")

    def test_api_key_should_only_be_validated_once_per_request(self):
        api_key, _ = self._create_api_key()
        with patch.object(
            UserModel,
            "get_valid_api_key_user",
            wraps=UserModel.get_valid_api_key_user,
        ) as validator:
            response = self._authenticate_with_api_key(api_key)

        self.assertEqual(response.status_code, 200)
        validator.assert_called_once()

    def test_auth_should_reject_invalid_api_key_states(self):
        invalid_states = (
            ("expired", {"expires_at": timezone.now() - datetime.timedelta(seconds=1)}),
            ("inactive", {"is_active": False}),
            ("blocked", {"is_blocked": True}),
        )

        for name, state in invalid_states:
            with self.subTest(name=name):
                api_key, key_user = self._create_api_key()
                UserModel.objects.filter(id=key_user.id).update(**state)
                self.assertEqual(self._authenticate_with_api_key(api_key).status_code, 401)

    def test_auth_should_reject_api_key_with_invalid_owner_state(self):
        for name, state in (("inactive", {"is_active": False}), ("blocked", {"is_blocked": True})):
            with self.subTest(name=name):
                api_key, _ = self._create_api_key()
                UserModel.objects.filter(id=self.gitHubUser.id).update(**state)
                self.assertEqual(self._authenticate_with_api_key(api_key).status_code, 401)
                UserModel.objects.filter(id=self.gitHubUser.id).update(
                    is_active=True, is_blocked=False
                )

    def test_api_key_should_preserve_owner_chain(self):
        api_key, parent = self._create_api_key()
        headers = copy.copy(self.github_request_headers)
        headers["X-CSRF-Token"] = ""
        headers["X-Auth-Token"] = ""
        headers["Authorization"] = api_key

        response = self.client.post(
            "/user/apikey/create/",
            headers=headers,
            data=json.dumps(self.keydata),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        created = response.json()["_result"]
        self.assertEqual(created["api_key"]["owner"]["id"], parent.id)

        UserModel.objects.filter(id=self.gitHubUser.id).update(is_blocked=True)
        self.assertEqual(
            self._authenticate_with_api_key(created["token"]).status_code, 401
        )

    @override_settings(AUTH_PROVIDERS=["github", "orcid", "gitlab", "native"])
    def test_auth_should_reject_api_key_when_provider_is_disabled(self):
        api_key, _ = self._create_api_key()
        self.assertEqual(self._authenticate_with_api_key(api_key).status_code, 401)

    def test_auth_should_reject_api_key_with_unconfigured_owner_provider(self):
        api_key, _ = self._create_api_key()
        with self.settings(AUTH_PROVIDERS=["orcid", "apikey"]):
            self.assertEqual(
                self._authenticate_with_api_key(api_key).status_code, 401
            )

    def test_auth_should_validate_legacy_api_key_owner_chain(self):
        _, parent = self._create_api_key()
        token = "apk_general_" + secrets.token_hex(32)
        UserModel.objects.create(
            username="api_legacy_child",
            auth_provider="apikey",
            client_ts="general",
            created_at=timezone.now(),
            api_key=make_hash(token),
            owner=parent,
        )

        self.assertEqual(self._authenticate_with_api_key(token).status_code, 200)
        UserModel.objects.filter(id=self.gitHubUser.id).update(is_blocked=True)
        self.assertEqual(self._authenticate_with_api_key(token).status_code, 401)

    def test_auth_should_reject_invalid_intermediate_api_key_states(self):
        invalid_states = (
            ("expired", {"expires_at": timezone.now() - datetime.timedelta(seconds=1)}),
            ("inactive", {"is_active": False}),
            ("blocked", {"is_blocked": True}),
        )

        for name, state in invalid_states:
            with self.subTest(name=name):
                _, parent = self._create_api_key()
                token = "apk_general_" + secrets.token_hex(32)
                UserModel.objects.create(
                    username="api_nested_" + secrets.token_urlsafe(16),
                    auth_provider="apikey",
                    client_ts="general",
                    created_at=timezone.now(),
                    api_key=make_hash(token),
                    owner=parent,
                )
                UserModel.objects.filter(id=parent.id).update(**state)

                self.assertEqual(
                    self._authenticate_with_api_key(token).status_code, 401
                )

    def test_auth_should_accept_deep_legacy_api_key_chain(self):
        owner = self.gitHubUser
        for index in range(MAX_API_KEY_OWNER_DEPTH + 1):
            token = "apk_general_" + secrets.token_hex(32)
            owner = UserModel.objects.create(
                username=f"api_legacy_{index}",
                auth_provider="apikey",
                client_ts="general",
                created_at=timezone.now(),
                api_key=make_hash(token),
                owner=owner,
            )

        self.assertEqual(self._authenticate_with_api_key(token).status_code, 200)

    def _create_api_key(self):
        response = self.client.post(
            "/user/apikey/create/",
            headers=self.github_request_headers,
            data=json.dumps(self.keydata),
            content_type="application/json",
        )
        api_key = response.json()["_result"]["token"]
        return api_key, UserModel.objects.get(api_key=make_hash(api_key))

    def _authenticate_with_api_key(self, api_key):
        headers = copy.copy(self.github_request_headers)
        headers["X-CSRF-Token"] = ""
        headers["X-Auth-Token"] = ""
        headers["Authorization"] = api_key
        return self.client.get(self.auth_url, headers=headers)

    @override_settings(AUTH_COOKIE_PARTITIONED_ORIGINS=["frontend.test"])
    def test_logout_should_delete_partitioned_jwt_cookie(self):
        headers = copy.copy(self.github_request_headers)
        headers["Origin"] = "https://frontend.test"
        response = self.client.post("/user/logout/", headers=headers)

        jwt_cookie = response.cookies.get("jwt")
        self.assertIsNotNone(jwt_cookie)
        self.assertEqual(jwt_cookie["max-age"], 0)
        self.assertTrue(jwt_cookie["secure"])
        self.assertEqual(jwt_cookie["samesite"], "None")
        self.assertTrue(jwt_cookie["partitioned"])
        self.assertIn("no-store", response["Cache-Control"])

    def test_logout_should_reject_get_requests(self):
        response = self.client.get("/user/logout/")
        self.assertEqual(response.status_code, 405)

    def test_auth_should_fail_with_wrong_api_key(self):
        headers = copy.copy(self.github_request_headers)
        response = self.client.post(
            "/user/apikey/create/",
            headers=headers,
            data=json.dumps(self.keydata),
            content_type="application/json",
        )
        api_key = response.json().get("_result").get("token")

        # we empty these to make sure auth is done only with api key
        headers["X-CSRF-Token"] = ""
        headers["X-Auth-Token"] = ""
        headers["Authorization"] = api_key + "some_manuplation"
        response = self.client.get(self.auth_url, headers=headers)
        self.assertEqual(response.status_code, 401)
