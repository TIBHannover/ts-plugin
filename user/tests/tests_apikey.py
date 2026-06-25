from user_service.libs.test_config import BaseTest
from user_service.libs.test_helpers import TestHelper
import copy
import json


class TestApiKey(BaseTest):
    @classmethod
    def setUpTestData(self) -> None:
        super().setUpTestData()
        self.existing_api_key = TestHelper.createApiKeyUser(
            user=self.gitHubUser,
            name="project_u",
            title="existing api key",
            description="this is existing api key",
        )

        self.keydata = {
            "name": "project_x",
            "title": "Test API Key",
            "description": "this is a test API Key",
            "expires_at": None,
        }
        self.update_keydata = {
            "name": "project_name_updated",
            "title": "updated Test API Key",
            "description": "this is the updated test API Key",
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

    def test_api_key_creation_should_fail_without_title(self):
        headers = copy.copy(self.github_request_headers)
        data = copy.copy(self.keydata)
        data.pop("title")
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
        self.assertTrue(response.json()["_result"]["token"].startswith("apk_general_"))
        self.assertEqual(
            len(response.json()["_result"]["token"]), 76
        )  # api_general_ + 32 hex

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
        self.assertEqual(response.status_code, 401)

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

    def test_api_key_update_should_fail_without_title(self):
        headers = copy.copy(self.github_request_headers)
        data = copy.copy(self.update_keydata)
        data["id"] = self.existing_api_key.id
        data.pop("title")
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

    def test_api_key_deletion_should_fail_for_guest(self):
        headers = copy.copy(self.guest_request_headers)
        response = self.client.delete(
            self.url + "delete/",
            headers=headers,
            data=json.dumps({"id": self.existing_api_key.id}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_api_key_deletion_should_fail_for_non_owner_user(self):
        headers = copy.copy(self.orcid_request_headers)
        response = self.client.delete(
            self.url + "delete/",
            headers=headers,
            data=json.dumps({"id": self.existing_api_key.id}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_api_key_deletion_should_success(self):
        headers = copy.copy(self.github_request_headers)
        response = self.client.delete(
            self.url + "delete/",
            headers=headers,
            data=json.dumps({"id": self.existing_api_key.id}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["_result"]["deleted"], True)

    def test_api_key_list_should_fail_for_guest(self):
        headers = copy.copy(self.guest_request_headers)
        response = self.client.get(
            self.url + "get/",
            headers=headers,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_api_key_list_should_contains_nothing_for_orcid_user(self):
        headers = copy.copy(self.orcid_request_headers)
        response = self.client.get(
            self.url + "get/",
            headers=headers,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["_result"]["api_keys"]), 0)

    def test_api_key_list_should_contains_one_key_for_github_user(self):
        headers = copy.copy(self.github_request_headers)
        response = self.client.get(
            self.url + "get/",
            headers=headers,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["_result"]["api_keys"]), 1)
        self.assertEqual(
            response.json()["_result"]["api_keys"][0]["owner"]["id"], self.gitHubUser.id
        )
