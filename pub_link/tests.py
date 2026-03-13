import copy
from django.test import TestCase
from user_service.libs.test_config import BaseTest
from user_service.libs.test_helpers import TestHelper
import json


class TestPubLink(TestCase, BaseTest):
    @classmethod
    def setUpTestData(self) -> None:
        self.pub_link_creation_url = "/pub_link/create/"
        self.pub_link_get_url = "/pub_link/get/"
        self.pub_link_delete_url = "/pub_link/delete/"
        self.orcidUser = TestHelper.createOrcidUser()
        self.gitHubUser = TestHelper.createGitHubUser()
        self.github_user_jwt = TestHelper.generate_jwt(
            {}, self.gitHubUser.username, self.github_access_token
        )
        self.orcid_user_jwt = TestHelper.generate_jwt(
            {},
            self.orcidUser.username,
            self.orcid_access_token,
            self.orcid_id,
        )
        self.ontologyId = "vibso"
        self.crossRefDoiUrl = "https://doi.org/10.1038/s41570-023-00502-0"
        self.dataCiteDoiUrl = "https://doi.org/10.48550/arXiv.2402.17496"
        self.crossRefDoiId = "10.1038/s41570-023-00502-0"
        self.dataCiteDoiId = "10.48550/arXiv.2402.17496"
        self.invalidDoi = "3434/invalid"
        self.existing_pub_link = TestHelper.create_pub_link(
            self.gitHubUser, self.crossRefDoiId, self.ontologyId
        )

    def test_pub_link_creation_should_fail_for_guest_user(self):
        headers = copy.copy(self.github_request_headers)
        token_without_username = TestHelper.generate_jwt(
            {}, "not_A_username", self.github_access_token
        )
        self.client.cookies["jwt"] = token_without_username
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
        self.client.cookies["jwt"] = self.github_user_jwt
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
        self.client.cookies["jwt"] = self.github_user_jwt
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
        self.client.cookies["jwt"] = self.github_user_jwt
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
        self.client.cookies["jwt"] = self.github_user_jwt
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
        self.client.cookies["jwt"] = self.github_user_jwt
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
        self.client.cookies["jwt"] = self.github_user_jwt
        response = self.client.post(
            self.pub_link_creation_url,
            headers=headers,
            data=json.dumps(
                {"doi": self.dataCiteDoiUrl, "ontology_id": self.ontologyId}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    def test_pub_link_get_should_success_with_crossref_doi_id(self):
        headers = copy.copy(self.github_request_headers)
        self.client.cookies["jwt"] = self.github_user_jwt
        response = self.client.get(
            self.pub_link_creation_url,
            headers=headers,
            data=json.dumps(
                {"doi": self.crossRefDoiId, "ontology_id": self.ontologyId}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    def test_pub_link_get_should_success_with_datacite_doi_id(self):
        headers = copy.copy(self.github_request_headers)
        self.client.cookies["jwt"] = self.github_user_jwt
        response = self.client.get(
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
            self.pub_link_get_url + self.ontologyId + "/",
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
        self.client.cookies["jwt"] = self.github_user_jwt
        response = self.client.delete(
            self.pub_link_delete_url + str(self.existing_pub_link["id"]) + "/",
            headers=headers,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["_result"]["deleted"], True)
