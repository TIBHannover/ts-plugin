import copy
from user_service.libs.test_config import BaseTest
from user_service.libs.test_helpers import TestHelper
import json


class TestCollection(BaseTest):
    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.collection = {
            "title": "Test creation",
            "content": "this is a test collection",
            "ontology_ids": ["vibso", "chmo"],
        }
        cls.test_collection_for_db = TestHelper.create_collection(
            user=cls.gitHubUser,
            title="Test update",
            content="this is a test collection",
            ontology_ids=["vibso"],
        ).to_dict()

    def test_collection_creation_should_fail_for_guest(self):
        headers = copy.copy(self.guest_request_headers)
        url = "/collection/create/"
        response = self.client.post(
            url,
            headers=headers,
            data=json.dumps(self.collection),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_collection_creation_should_fail_without_title(self):
        headers = copy.copy(self.github_request_headers)
        data = copy.copy(self.collection)
        data.pop("title")
        url = "/collection/create/"
        response = self.client.post(
            url, headers=headers, data=json.dumps(data), content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Mandatory Fields are missing", response.content.decode())

    def test_collection_creation_should_success(self):
        headers = copy.copy(self.github_request_headers)
        url = "/collection/create/"
        response = self.client.post(
            url,
            headers=headers,
            data=json.dumps(self.collection),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["_result"]["collection"]["title"], self.collection["title"]
        )

    def test_get_collection_should_fail_for_non_owner_user(self):
        """
        Collection is created by github user, but trying to get collection by orcid user
        """
        headers = copy.copy(self.orcid_request_headers)
        url = "/collection/get/" + str(self.test_collection_for_db["id"]) + "/"
        response = self.client.get(url, headers=headers)
        self.assertEqual(response.status_code, 404)

    def test_get_collection_should_fail_for_non_existing_id(self):
        headers = copy.copy(self.github_request_headers)
        url = "/collection/get/non_existing_id/"
        response = self.client.get(url, headers=headers)
        self.assertEqual(response.status_code, 404)

    def test_get_collection_should_success(self):
        headers = copy.copy(self.github_request_headers)
        url = "/collection/get/" + str(self.test_collection_for_db["id"]) + "/"
        response = self.client.get(url, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["_result"]["collection"]["title"],
            self.test_collection_for_db["title"],
        )

    def test_get_collection_list_should_success(self):
        headers = copy.copy(self.github_request_headers)
        url = "/collection/get_list/"
        response = self.client.get(url, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["_result"]["collections"]), 1)

    def test_collection_update_should_fail_for_non_owner_user(self):
        """
        Collection is created by github user, but trying to update collection by orcid user
        """
        headers = copy.copy(self.orcid_request_headers)
        url = "/collection/update/" + str(self.test_collection_for_db["id"]) + "/"
        response = self.client.put(
            url,
            headers=headers,
            data=json.dumps(self.collection),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_collection_update_should_success(self):
        headers = copy.copy(self.github_request_headers)
        url = "/collection/update/" + str(self.test_collection_for_db["id"]) + "/"
        response = self.client.put(
            url,
            headers=headers,
            data=json.dumps(self.collection),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    def test_collection_delete_should_fail_for_non_owner_user(self):
        """
        Collection is created by github user, but trying to update collection by orcid user
        """
        headers = copy.copy(self.orcid_request_headers)
        url = "/collection/delete/" + str(self.test_collection_for_db["id"]) + "/"
        response = self.client.delete(url, headers=headers)
        self.assertEqual(response.status_code, 404)

    def test_collection_delete_should_success(self):
        headers = copy.copy(self.github_request_headers)
        url = "/collection/delete/" + str(self.test_collection_for_db["id"]) + "/"
        response = self.client.delete(url, headers=headers)
        self.assertEqual(response.status_code, 200)
