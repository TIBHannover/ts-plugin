import copy
from django.test import TestCase
from user_service.libs.test_config import BaseTest
from user_service.libs.test_helpers import TestHelper
import json


class TestDeletion(TestCase, BaseTest):
    @classmethod
    def setUpTestData(self) -> None:
        self.orcidUser = TestHelper.createOrcidUser()
        self.gitHubUser = TestHelper.createGitHubUser()
        self.note = TestHelper.createNote(user=self.gitHubUser)
        self.comment = TestHelper.createCommentForNote(
            user=self.gitHubUser, note=self.note
        )
        self.note_comment_delete_url = "/note/delete/"
        self.github_user_jwt = TestHelper.generate_jwt(
            {}, self.gitHubUser.username, self.github_access_token
        )
        self.orcid_user_jwt = TestHelper.generate_jwt(
            {},
            self.orcidUser.username,
            self.orcid_access_token,
            self.orcid_id,
        )

    def test_delete_should_fail_without_object_id(self):
        headers = copy.copy(self.github_request_headers)
        post_data = {"objectType": "note", "ontology_id": self.test_ontology_id}
        self.client.cookies["jwt"] = self.github_user_jwt
        response = self.client.delete(
            self.note_comment_delete_url,
            headers=headers,
            data=json.dumps(post_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Mandatory Fields are missing", response.content.decode())

    def test_delete_should_fail_without_object_type(self):
        headers = copy.copy(self.github_request_headers)
        post_data = {"objectId": self.note.id, "ontology_id": self.test_ontology_id}
        self.client.cookies["jwt"] = self.github_user_jwt
        response = self.client.delete(
            self.note_comment_delete_url,
            headers=headers,
            data=json.dumps(post_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Mandatory Fields are missing", response.content.decode())

    def test_delete_should_fail_with_not_authorized_user(self):
        headers = copy.copy(self.orcid_request_headers)
        post_data = {
            "objectId": self.note.id,
            "objectType": "note",
            "ontology_id": self.test_ontology_id,
        }
        self.client.cookies["jwt"] = self.orcid_user_jwt
        response = self.client.delete(
            self.note_comment_delete_url,
            headers=headers,
            data=json.dumps(post_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("Not Authorized", response.content.decode())

    def test_delete_should_fail_with_guest_user(self):
        headers = copy.copy(self.guest_request_headers)
        post_data = {
            "objectId": self.note.id,
            "objectType": "note",
            "ontology_id": self.test_ontology_id,
        }
        response = self.client.delete(
            self.note_comment_delete_url,
            headers=headers,
            data=json.dumps(post_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("request is not valid", response.content.decode())

    def test_delete_should_success_for_note(self):
        headers = copy.copy(self.github_request_headers)
        post_data = {
            "objectId": self.note.id,
            "objectType": "note",
            "ontology_id": self.test_ontology_id,
        }
        self.client.cookies["jwt"] = self.github_user_jwt
        response = self.client.delete(
            self.note_comment_delete_url,
            headers=headers,
            data=json.dumps(post_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["_result"]["deleted"], True)

    def test_delete_should_success_for_comment(self):
        headers = copy.copy(self.github_request_headers)
        self.client.cookies["jwt"] = self.github_user_jwt
        post_data = {
            "objectId": self.comment.id,
            "objectType": "comment",
            "ontology_id": self.test_ontology_id,
        }
        response = self.client.delete(
            self.note_comment_delete_url,
            headers=headers,
            data=json.dumps(post_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["_result"]["deleted"], True)
