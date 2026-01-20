import copy
from django.test import TestCase
from user_service.libs.test_config import BaseTest
from user_service.libs.test_helpers import TestHelper
import json


class TestNoteCreation(TestCase, BaseTest):
    @classmethod
    def setUpTestData(self) -> None:
        self.note = {
            "title": "Test Note",
            "content": "Test Content",
            "ontology_id": "vibso",
            "semantic_component_type": "class",
            "semantic_component_iri": "http://test_iri",
            "semantic_component_label": "Test Label",
            "visibility": "public",
        }
        self.note_creation_url = "/note/create/"
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

    def test_note_creation_should_fail_without_username(self):
        headers = copy.copy(self.github_request_headers)
        token_without_username = TestHelper.generate_jwt(
            {}, "not_A_username", self.github_access_token
        )
        self.client.cookies["jwt"] = token_without_username
        response = self.client.post(
            self.note_creation_url,
            headers=headers,
            data=json.dumps(self.note),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("Not Authorized user", response.content.decode())

    def test_note_creation_should_fail_without_title(self):
        headers = copy.copy(self.github_request_headers)
        post_data = copy.copy(self.note)
        del post_data["title"]
        self.client.cookies["jwt"] = self.github_user_jwt
        response = self.client.post(
            self.note_creation_url,
            headers=headers,
            data=json.dumps(post_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Mandatory Fields are missing", response.content.decode())

    def test_note_creation_should_fail_without_content(self):
        headers = copy.copy(self.github_request_headers)
        post_data = copy.copy(self.note)
        del post_data["content"]
        self.client.cookies["jwt"] = self.github_user_jwt
        response = self.client.post(
            self.note_creation_url,
            headers=headers,
            data=json.dumps(post_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Mandatory Fields are missing", response.content.decode())

    def test_note_creation_should_fail_without_ontologyId(self):
        headers = copy.copy(self.github_request_headers)
        post_data = copy.copy(self.note)
        del post_data["ontology_id"]
        self.client.cookies["jwt"] = self.github_user_jwt
        response = self.client.post(
            self.note_creation_url,
            headers=headers,
            data=json.dumps(post_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Mandatory Fields are missing", response.content.decode())

    def test_note_creation_should_fail_without_artifact_type(self):
        headers = copy.copy(self.github_request_headers)
        post_data = copy.copy(self.note)
        del post_data["semantic_component_type"]
        self.client.cookies["jwt"] = self.github_user_jwt
        response = self.client.post(
            self.note_creation_url,
            headers=headers,
            data=json.dumps(post_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Mandatory Fields are missing", response.content.decode())

    def test_note_creation_should_fail_without_artifact_iri(self):
        headers = copy.copy(self.github_request_headers)
        post_data = copy.copy(self.note)
        del post_data["semantic_component_iri"]
        self.client.cookies["jwt"] = self.github_user_jwt
        response = self.client.post(
            self.note_creation_url,
            headers=headers,
            data=json.dumps(post_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Mandatory Fields are missing", response.content.decode())

    def test_note_creation_should_success(self):
        headers = copy.copy(self.github_request_headers)
        self.client.cookies["jwt"] = self.github_user_jwt
        response = self.client.post(
            self.note_creation_url,
            headers=headers,
            data=json.dumps(self.note),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            "Test Note", response.json()["_result"]["note_created"]["title"]
        )

    def test_note_creation_should_set_visibility_to_me_when_not_given(self):
        headers = copy.copy(self.github_request_headers)
        post_data = copy.copy(self.note)
        del post_data["visibility"]
        self.client.cookies["jwt"] = self.github_user_jwt
        response = self.client.post(
            self.note_creation_url,
            headers=headers,
            data=json.dumps(post_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["_result"]["note_created"]["visibility"], "me")

    def test_note_creation_should_success_with_parent_ontology(self):
        headers = copy.copy(self.github_request_headers)
        headers["Content-Type"] = "application/json"
        post_data = copy.copy(self.note)
        post_data["parentOntology"] = self.test_parent_ontology_id
        self.client.cookies["jwt"] = self.github_user_jwt
        response = self.client.post(
            self.note_creation_url,
            headers=headers,
            data=json.dumps(post_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["_result"]["note_created"]["parent_ontology"],
            self.test_parent_ontology_id,
        )
        self.assertIn("Test Note", response.json()["_result"]["note_created"]["title"])
