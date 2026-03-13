from user_service.libs.test_config import BaseTest
from user_service.libs.test_helpers import TestHelper
import copy
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
        self.assertIn("Not Authorized user token", response.content.decode())

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
        response = self.client.get(self.auth_url, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("_result").get("response"), "closed")

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
