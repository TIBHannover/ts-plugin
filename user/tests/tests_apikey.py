from django.test import TestCase
from user_service.libs.test_config import BaseTest
from user_service.libs.test_helpers import TestHelper
import copy
import json


class TestApiKey(TestCase, BaseTest):

    @classmethod
    def setUpTestData(self) -> None:
        self.user = TestHelper.createGitHubUser()
        self.other_user = TestHelper.createOrcidUser()
        self.existing_api_key = TestHelper.createUserApiKey(
            user=self.user,
            name="existing api key",
            description="this is existing api key",
            alt_username="existing_api_key",
        )

        self.keydata = {
            "name": "Test API Key",
            "description": "this is a test API Key",
            "alt_username": "test_api_key",
            "expires_at": None,
        }
        self.update_keydata = {
            "name": "updated Test API Key",
            "description": "this is the updated test API Key",
            "alt_username": "updated_test_api_key",
            "expires_at": None,
        }
        self.url = "/user/apikey/"

    def test_api_key_creation_should_fail_for_guest(self):
        headers = copy.copy(self.guest_request_headers)
        response = self.client.post(
            self.url + "create/",
            headers=headers,
            data=json.dumps(self.keydata),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_api_key_creation_should_fail_without_name(self):
        headers = copy.copy(self.github_request_headers)
        data = copy.copy(self.keydata)
        data.pop("name")
        response = self.client.post(
            self.url + "create/",
            headers=headers,
            data=json.dumps(data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_api_key_creation_should_success(self):
        headers = copy.copy(self.github_request_headers)
        response = self.client.post(
            self.url + "create/",
            headers=headers,
            data=json.dumps(self.keydata),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["_result"]["token"].startswith("apk_"))
        self.assertEqual(len(response.json()["_result"]["token"]), 36)

    def test_api_key_update_should_fail_for_guest(self):
        headers = copy.copy(self.guest_request_headers)
        data = copy.copy(self.update_keydata)
        data["id"] = self.existing_api_key.id
        response = self.client.put(
            self.url + "update/",
            headers=headers,
            data=json.dumps(data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_api_key_update_should_fail_for_non_owner_user(self):
        headers = copy.copy(self.orcid_request_headers)
        data = copy.copy(self.update_keydata)
        data["id"] = self.existing_api_key.id
        response = self.client.put(
            self.url + "update/",
            headers=headers,
            data=json.dumps(data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_api_key_update_should_fail_without_name(self):
        headers = copy.copy(self.github_request_headers)
        data = copy.copy(self.update_keydata)
        data["id"] = self.existing_api_key.id
        data.pop("name")
        response = self.client.put(
            self.url + "update/",
            headers=headers,
            data=json.dumps(data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_api_key_update_should_success(self):
        headers = copy.copy(self.github_request_headers)
        data = copy.copy(self.update_keydata)
        data["id"] = self.existing_api_key.id
        response = self.client.put(
            self.url + "update/",
            headers=headers,
            data=json.dumps(data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["_result"]["updated"]["name"], self.update_keydata["name"]
        )
