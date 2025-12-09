from django.test import TestCase
from user_service.libs.test_config import BaseTest
from user_service.libs.test_helpers import TestHelper
import copy
import json


class TestAdminAccess(TestCase, BaseTest):
    @classmethod
    def setUpTestData(self) -> None:
        """
        Test Scenario:
            Orcid User creates some notes and comments for one ontology.
            Github user is the admin for that ontology. So she should be able to edit/delete Orcid user notes and comments
        """

        self.edit_internal_note_data = {
            "title": "Edited internal",
            "content": "New Test Content",
            "ontology_id": "vibso",
            "semantic_component_type": "class",
            "semantic_component_iri": "http://test_iri",
            "semantic_component_label": "Test Label",
            "visibility": "internal",
        }

        self.edit_me_note_data = {
            "title": "Edited me",
            "content": "New Test Content",
            "ontology_id": "vibso",
            "semantic_component_type": "class",
            "semantic_component_iri": "http://test_iri",
            "semantic_component_label": "Test Label",
            "visibility": "me",
        }

        self.orcidUser = TestHelper.createOrcidUser()
        self.gitHubUser = TestHelper.createGitHubUser()
        self.internal_vis_note = TestHelper.createNote(self.orcidUser, "internal")
        self.edit_internal_note_data["noteId"] = self.internal_vis_note.id
        self.me_vis_note = TestHelper.createNote(self.orcidUser, "me")
        self.edit_me_note_data["noteId"] = self.me_vis_note.id
        self.internal_vis_note_comment = TestHelper.createCommentForNote(
            self.orcidUser, self.internal_vis_note
        )
        self.me_vis_note_comment = TestHelper.createCommentForNote(
            self.orcidUser, self.me_vis_note
        )
        TestHelper.createRole(self.gitHubUser, "vibso", "ontology", "admin")

    def test_note_update_admin_should_work_for_admin(self):
        headers = copy.copy(self.github_request_headers)
        note_update_url = "/note/update/"
        response = self.client.put(
            note_update_url,
            headers=headers,
            data=json.dumps(self.edit_internal_note_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["_result"]["note_updated"]["title"], "Edited internal"
        )

    def test_note_comment_admin_edit_should_success(self):
        headers = copy.copy(self.github_request_headers)
        post_data = {
            "content": "edited comment by admin",
            "ontology_id": self.test_ontology_id,
        }
        post_data["comment_id"] = self.internal_vis_note_comment.id
        comment_update_url = "/note/update_comment/"
        response = self.client.put(
            comment_update_url,
            headers=headers,
            data=json.dumps(post_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["_result"]["comment_updated"]["content"],
            "edited comment by admin",
        )

    def test_delete_admin_should_success_for_note(self):
        headers = copy.copy(self.github_request_headers)
        post_data = {
            "objectId": self.edit_internal_note_data["noteId"],
            "objectType": "note",
            "ontology_id": self.test_ontology_id,
        }
        note_comment_delete_url = "/note/delete/"
        response = self.client.delete(
            note_comment_delete_url,
            headers=headers,
            data=json.dumps(post_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["_result"]["deleted"], True)
        # self.assertEqual(self.internal_vis_note.active, False)

    def test_delete_admin_should_success_for_comment(self):
        headers = copy.copy(self.github_request_headers)
        post_data = {
            "objectId": self.internal_vis_note_comment.id,
            "objectType": "comment",
            "ontology_id": self.test_ontology_id,
        }
        note_comment_delete_url = "/note/delete/"
        response = self.client.delete(
            note_comment_delete_url,
            headers=headers,
            data=json.dumps(post_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["_result"]["deleted"], True)
        # self.assertEqual(self.internal_vis_note_comment.active, False)

    def test_delete_admin_should_fail_for_me_note(self):
        headers = copy.copy(self.github_request_headers)
        post_data = {
            "objectId": self.edit_me_note_data["noteId"],
            "objectType": "note",
            "ontology_id": self.test_ontology_id,
        }
        note_comment_delete_url = "/note/delete/"
        response = self.client.delete(
            note_comment_delete_url,
            headers=headers,
            data=json.dumps(post_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_delete_admin_should_fail_for_me_comment(self):
        headers = copy.copy(self.github_request_headers)
        post_data = {
            "objectId": self.me_vis_note_comment.id,
            "objectType": "comment",
            "ontology_id": self.test_ontology_id,
        }
        note_comment_delete_url = "/note/delete/"
        response = self.client.delete(
            note_comment_delete_url,
            headers=headers,
            data=json.dumps(post_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
