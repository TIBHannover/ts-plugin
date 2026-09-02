from user_service.libs.test_config import BaseTest
from user_service.libs.test_helpers import TestHelper
from django.conf import settings
from django.test import override_settings
from jose import jwt
import copy
import datetime
import json


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
