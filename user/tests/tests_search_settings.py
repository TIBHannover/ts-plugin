from django.test import TestCase
from user_service.libs.test_config import BaseTest
from user_service.libs.test_helpers import TestHelper
import copy
import json


class TestSearchSetting(TestCase, BaseTest):

    @classmethod
    def setUpTestData(self) -> None:
        self.user = TestHelper.createGitHubUser()
        TestHelper.createOrcidUser()

        self.settings_dict = {
            "title": "Test setting",
            "description": "this is a test collection",
            "setting": {"test_field": "test_value"},
        }
        self.test_setting_for_db = TestHelper.create_search_setting(
            user=self.user,
            title="Test setting For DB",
            description="this is a test setting",
            settings={"test_field": "test_value"},
        ).to_dict()
        self.url = "/user/search_setting/"

    def test_setting_creation_should_fail_for_guest(self):
        headers = copy.copy(self.guest_request_headers)
        response = self.client.post(
            self.url,
            headers=headers,
            data=json.dumps(self.settings_dict),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_setting_creation_should_fail_without_title(self):
        headers = copy.copy(self.github_request_headers)
        data = copy.copy(self.settings_dict)
        data.pop("title")
        response = self.client.post(
            self.url,
            headers=headers,
            data=json.dumps(data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_setting_creation_should_success(self):
        headers = copy.copy(self.github_request_headers)
        response = self.client.post(
            self.url,
            headers=headers,
            data=json.dumps(self.settings_dict),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["_result"]["saved"]["title"], self.settings_dict["title"]
        )

    def test_get_setting_should_fail_for_non_owner_user(self):
        """
        Setting is created by github user, but trying to get collection by orcid user
        """
        headers = copy.copy(self.orcid_request_headers)
        url = self.url + str(self.test_setting_for_db["id"]) + "/"
        response = self.client.get(url, headers=headers)
        self.assertEqual(response.status_code, 404)

    def test_get_setting_should_fail_for_non_existing_id(self):
        headers = copy.copy(self.github_request_headers)
        url = self.url + "non_existing_id/"
        response = self.client.get(url, headers=headers)
        self.assertEqual(response.status_code, 404)

    def test_get_setting_should_success(self):
        headers = copy.copy(self.github_request_headers)
        url = self.url + str(self.test_setting_for_db["id"]) + "/"
        response = self.client.get(url, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["_result"]["setting"]["title"],
            self.test_setting_for_db["title"],
        )

    def test_get_setting_list_should_success(self):
        headers = copy.copy(self.github_request_headers)
        response = self.client.get(
            self.url, headers=headers, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["_result"]["settings"]), 1)

    def test_setting_update_should_fail_for_non_owner_user(self):
        """
        Setting is created by github user, but trying to update collection by orcid user
        """
        headers = copy.copy(self.orcid_request_headers)
        url = self.url + str(self.test_setting_for_db["id"]) + "/"
        response = self.client.put(
            url,
            headers=headers,
            data=json.dumps(self.settings_dict),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_setting_update_should_success(self):
        headers = copy.copy(self.github_request_headers)
        url = self.url + str(self.test_setting_for_db["id"]) + "/"
        response = self.client.put(
            url,
            headers=headers,
            data=json.dumps(self.settings_dict),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    def test_setting_delete_should_fail_for_non_owner_user(self):
        """
        Setting is created by github user, but trying to update collection by orcid user
        """
        headers = copy.copy(self.orcid_request_headers)
        url = self.url + str(self.test_setting_for_db["id"]) + "/"
        response = self.client.delete(url, headers=headers)
        self.assertEqual(response.status_code, 404)

    def test_setting_delete_should_success(self):
        headers = copy.copy(self.github_request_headers)
        url = self.url + str(self.test_setting_for_db["id"]) + "/"
        response = self.client.delete(url, headers=headers)
        self.assertEqual(response.status_code, 200)
