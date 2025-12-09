from django.test import TestCase
from user_service.libs.test_config import BaseTest
from user_service.libs.test_helpers import TestHelper
import copy
import json


class TestNoteComment(TestCase, BaseTest):
    @classmethod
    def setUpTestData(self) -> None:
        self.comment_for_public_note = {"content": "Test Comment"}
        self.comment_for_private_note = {"content": "Test Comment"}
        self.comment_create_url = "/note/create_comment/"
        self.comment_update_url = "/note/update_comment/"
        self.gitHubUser = TestHelper.createGitHubUser()
        self.orcidUser = TestHelper.createOrcidUser()
        self.public_note = TestHelper.createNote(user=self.gitHubUser)
        self.private_note = TestHelper.createNote(user=self.gitHubUser, visibility="me")
        self.comment_for_public_note["noteId"] = self.public_note.id
        self.comment_for_private_note["noteId"] = self.private_note.id
        self.comment_to_edit = TestHelper.createCommentForNote(
            user=self.gitHubUser, note=self.public_note
        )

    def test_note_comment_should_fail_with_wrong_noteId(self):
        headers = copy.copy(self.github_request_headers)
        post_data = copy.copy(self.comment_for_public_note)
        post_data["noteId"] = 12345
        response = self.client.post(
            self.comment_create_url,
            headers=headers,
            data=json.dumps(post_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("Note does not exist", response.content.decode())

    def test_note_comment_should_fail_for_guest_user(self):
        headers = copy.copy(self.guest_request_headers)
        post_data = copy.copy(self.comment_for_public_note)
        response = self.client.post(
            self.comment_create_url,
            headers=headers,
            data=json.dumps(post_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("Not Authorize", response.content.decode())

    def test_note_comment_should_fail_for_user_who_are_not_private_note_owner(self):
        headers = copy.copy(self.orcid_request_headers)
        post_data = copy.copy(self.comment_for_private_note)
        response = self.client.post(
            self.comment_create_url,
            headers=headers,
            data=json.dumps(post_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("Note does not exist", response.content.decode())

    def test_note_comment_should_success(self):
        headers = copy.copy(self.github_request_headers)
        post_data = copy.copy(self.comment_for_private_note)
        response = self.client.post(
            self.comment_create_url,
            headers=headers,
            data=json.dumps(post_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["_result"]["comment_created"]["content"], "Test Comment"
        )

    ### Comment Edit ##

    def test_note_comment_edit_should_fail_with_wrong_commentId(self):
        headers = copy.copy(self.github_request_headers)
        post_data = {"content": "edited", "ontology_id": self.test_ontology_id}
        post_data["comment_id"] = 12345
        response = self.client.put(
            self.comment_update_url,
            headers=headers,
            data=json.dumps(post_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("Comment does not exist", response.content.decode())

    def test_note_comment_edit_should_fail_with_guest_user(self):
        headers = copy.copy(self.guest_request_headers)
        post_data = {"content": "edited", "ontology_id": self.test_ontology_id}
        post_data["comment_id"] = self.comment_to_edit.id
        response = self.client.put(
            self.comment_update_url,
            headers=headers,
            data=json.dumps(post_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("Not Authorized", response.content.decode())

    def test_note_comment_edit_should_fail_with_non_owner_user(self):
        headers = copy.copy(self.orcid_request_headers)
        post_data = {"content": "edited", "ontology_id": self.test_ontology_id}
        post_data["comment_id"] = self.comment_to_edit.id
        response = self.client.put(
            self.comment_update_url,
            headers=headers,
            data=json.dumps(post_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("Not Authorized", response.content.decode())

    def test_note_comment_edit_should_success(self):
        headers = copy.copy(self.github_request_headers)
        post_data = {"content": "edited", "ontology_id": self.test_ontology_id}
        post_data["comment_id"] = self.comment_to_edit.id
        response = self.client.put(
            self.comment_update_url,
            headers=headers,
            data=json.dumps(post_data),
            content_type="application/json",
        )
        assert (
            response.status_code == 200
            and response.json()["_result"]["comment_updated"]["content"] == "edited"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["_result"]["comment_updated"]["content"], "edited"
        )
