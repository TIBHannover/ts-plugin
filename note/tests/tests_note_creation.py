import copy
from user_service.libs.test_config import BaseTest
from user_service.libs.test_helpers import TestHelper
import json


class TestNoteCreation(BaseTest):
    @classmethod
    def setUpTestData(self) -> None:
        super().setUpTestData()
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

    def test_note_creation_should_fail_without_username(self):
        headers = copy.copy(self.guest_request_headers)
        response = self.client.post(
            self.note_creation_url,
            headers=headers,
            data=json.dumps(self.note),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_note_creation_should_fail_without_title(self):
        headers = copy.copy(self.github_request_headers)
        post_data = copy.copy(self.note)
        del post_data["title"]
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
