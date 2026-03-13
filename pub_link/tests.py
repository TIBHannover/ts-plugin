import copy
from user_service.libs.test_config import BaseTest
from user_service.libs.test_helpers import TestHelper
import json


class TestPubLink(BaseTest):
    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.pub_link_creation_url = "/pub_link/create/"
        cls.pub_link_get_url = "/pub_link/get/"
        cls.pub_link_delete_url = "/pub_link/delete/"
        cls.ontologyId = "vibso"
        cls.crossRefDoiUrl = "https://doi.org/10.1038/s41570-023-00502-0"
        cls.dataCiteDoiUrl = "https://doi.org/10.48550/arXiv.2402.17496"
        cls.crossRefDoiId = "10.1038/s41570-023-00502-0"
        cls.dataCiteDoiId = "10.48550/arXiv.2402.17496"
        cls.invalidDoi = "3434/invalid"
        cls.ontology_id_in_db = "chmo"
        cls.existing_pub_link = TestHelper.create_pub_link(
            cls.gitHubUser, cls.crossRefDoiId, cls.ontology_id_in_db
        )

    def test_pub_link_creation_should_fail_for_guest_user(self):
        headers = copy.copy(self.guest_request_headers)
        response = self.client.post(
            self.pub_link_creation_url,
            headers=headers,
            data=json.dumps(
                {"doi": self.crossRefDoiId, "ontology_id": self.ontologyId}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_pub_link_creation_should_fail_for_invalid_doi(self):
        headers = copy.copy(self.github_request_headers)
        response = self.client.post(
            self.pub_link_creation_url,
            headers=headers,
            data=json.dumps({"doi": self.invalidDoi, "ontology_id": self.ontologyId}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid DOI", response.content.decode())

    def test_pub_link_creation_should_fail_without_ontology_id(self):
        headers = copy.copy(self.github_request_headers)
        response = self.client.post(
            self.pub_link_creation_url,
            headers=headers,
            data=json.dumps({"doi": self.crossRefDoiId}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Mandatory Fields are missing", response.content.decode())

    def test_pub_link_creation_should_fail_without_doi(self):
        headers = copy.copy(self.github_request_headers)
        response = self.client.post(
            self.pub_link_creation_url,
            headers=headers,
            data=json.dumps({"ontology_id": self.ontologyId}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Mandatory Fields are missing", response.content.decode())

    def test_pub_link_creation_should_success(self):
        headers = copy.copy(self.github_request_headers)
        response = self.client.post(
            self.pub_link_creation_url,
            headers=headers,
            data=json.dumps(
                {"doi": self.crossRefDoiId, "ontology_id": self.ontologyId}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    def test_pub_link_creation_should_success_with_crossref_doi_url(self):
        headers = copy.copy(self.github_request_headers)
        response = self.client.post(
            self.pub_link_creation_url,
            headers=headers,
            data=json.dumps(
                {"doi": self.crossRefDoiUrl, "ontology_id": self.ontologyId}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    def test_pub_link_creation_should_success_with_datacite_doi_url(self):
        headers = copy.copy(self.github_request_headers)
        response = self.client.post(
            self.pub_link_creation_url,
            headers=headers,
            data=json.dumps(
                {"doi": self.dataCiteDoiUrl, "ontology_id": self.ontologyId}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    def test_pub_link_creation_should_success_with_crossref_doi_id(self):
        headers = copy.copy(self.github_request_headers)
        response = self.client.post(
            self.pub_link_creation_url,
            headers=headers,
            data=json.dumps(
                {"doi": self.crossRefDoiId, "ontology_id": self.ontologyId}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    def test_pub_link_creation_should_success_with_datacite_doi_id(self):
        headers = copy.copy(self.github_request_headers)
        response = self.client.post(
            self.pub_link_creation_url,
            headers=headers,
            data=json.dumps(
                {"doi": self.dataCiteDoiId, "ontology_id": self.ontologyId}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    def test_pub_link_get_should_success(self):
        headers = copy.copy(self.guest_request_headers)
        response = self.client.get(
            self.pub_link_get_url + self.ontology_id_in_db + "/",
            headers=headers,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["_result"]["publications"][0]["doi"], self.crossRefDoiId
        )

    def test_pub_link_delete_should_fail_for_guest_user(self):
        headers = copy.copy(self.guest_request_headers)
        response = self.client.delete(
            self.pub_link_delete_url + str(self.existing_pub_link["id"]) + "/",
            headers=headers,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_pub_link_delete_should_fail_for_another_user(self):
        # github user is the creator of the pub link
        headers = copy.copy(self.orcid_request_headers)
        response = self.client.delete(
            self.pub_link_delete_url + str(self.existing_pub_link["id"]) + "/",
            headers=headers,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_pub_link_delete_should_success(self):
        headers = copy.copy(self.github_request_headers)
        response = self.client.delete(
            self.pub_link_delete_url + str(self.existing_pub_link["id"]) + "/",
            headers=headers,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["_result"]["deleted"], True)
