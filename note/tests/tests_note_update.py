import copy
from user_service.libs.test_config import BaseTest
from user_service.libs.test_helpers import TestHelper
import json


class TestNoteUpdate(BaseTest):
    @classmethod
    def setUpTestData(self) -> None:
        super().setUpTestData()
        self.edit_note_data = {
            "title": "Edited",
            "content": "New Test Content",
            "ontology_id": "vibso",
            "semantic_component_type": "class",
            "semantic_component_iri": "http://test_iri",
            "semantic_component_label": "Test Label",
            "visibility": "public",
        }
        self.note_update_url = "/note/update/"
        self.note = TestHelper.createNote(user=self.gitHubUser)
        self.edit_note_data["noteId"] = self.note.id

    def test_note_update_should_fail_without_noteId(self):
        headers = copy.copy(self.github_request_headers)
        post_data = copy.copy(self.edit_note_data)
        del post_data["noteId"]
        response = self.client.put(
            self.note_update_url,
            headers=headers,
            data=json.dumps(post_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Mandatory Fields are missing", response.content.decode())

    def test_note_update_should_fail_with_wrong_noteId(self):
        headers = copy.copy(self.github_request_headers)
        post_data = copy.copy(self.edit_note_data)
        post_data["noteId"] = 12345
        response = self.client.put(
            self.note_update_url,
            headers=headers,
            data=json.dumps(post_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("Note does not exist", response.content.decode())

    def test_note_update_should_fail_for_guest_user(self):
        headers = copy.copy(self.guest_request_headers)
        response = self.client.put(
            self.note_update_url,
            headers=headers,
            data=json.dumps(self.edit_note_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("request is not valid", response.content.decode())

    def test_note_update_should_fail_for_user_withoud_edit_access(self):
        # Note was created with a github user. Orcid user cannot edit.
        headers = copy.copy(self.orcid_request_headers)
        response = self.client.put(
            self.note_update_url,
            headers=headers,
            data=json.dumps(self.edit_note_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("Not Authorized", response.content.decode())

    def test_note_update_should_success(self):
        headers = copy.copy(self.github_request_headers)
        response = self.client.put(
            self.note_update_url,
            headers=headers,
            data=json.dumps(self.edit_note_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["_result"]["note_updated"]["title"], "Edited")

    def test_note_update_should_success_for_removing_parent_ontology(self):
        headers = copy.copy(self.github_request_headers)
        response = self.client.put(
            self.note_update_url,
            headers=headers,
            data=json.dumps(self.edit_note_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["_result"]["note_updated"]["title"], "Edited")
        self.assertEqual(
            response.json()["_result"]["note_updated"]["parent_ontology"], None
        )

    def test_note_update_should_success_for_adding_parent_ontology(self):
        headers = copy.copy(self.github_request_headers)
        post_data = copy.copy(self.edit_note_data)
        post_data["parentOntology"] = "chmo"
        response = self.client.put(
            self.note_update_url,
            headers=headers,
            data=json.dumps(post_data),
            content_type="application/json",
        )
        self.assertEqual(
            response.json()["_result"]["note_updated"]["parent_ontology"], "chmo"
        )
