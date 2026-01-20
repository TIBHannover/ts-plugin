from django.test import TestCase
from user_service.libs.test_config import BaseTest
import copy
import json
from user_service.libs.test_helpers import TestHelper


class TestReport(TestCase, BaseTest):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.report_form_data = {
            "objectType": "note",
            "objectId": 1,
            "content": "Test content for report",
            "ontology": "vibso",
        }

        cls.resolve_report_form_data = {
            "objectType": "note",
            "objectId": 1,
            "action": "none",
            "creatorUsername": "test-user",
        }

        cls.gitHubUser = TestHelper.createGitHubUser()
        cls.orcidUser = TestHelper.createOrcidUser()
        TestHelper.createSystemAdmin(cls.gitHubUser)
        note = TestHelper.createNote(cls.gitHubUser)
        cls.public_note_id = note.id
        cls.report_form_data["objectId"] = note.id
        cls.resolve_report_form_data["objectId"] = note.id
        cls.report_create_url = "/report/create/"
        cls.report_resolve_url = "/report/resolve/"
        cls.github_user_jwt = TestHelper.generate_jwt(
            {}, cls.gitHubUser.username, cls.github_access_token
        )
        cls.orcid_user_jwt = TestHelper.generate_jwt(
            {},
            cls.orcidUser.username,
            cls.orcid_access_token,
            cls.orcid_id,
        )

    def test_report_create_fail_for_guest_user(self):
        headers = copy.copy(self.guest_request_headers)
        response = self.client.post(
            self.report_create_url,
            headers=headers,
            data=json.dumps(self.report_form_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("request is not valid", response.content.decode())

    def test_report_create_success_user(self):
        headers = copy.copy(self.orcid_request_headers)
        self.client.cookies["jwt"] = self.orcid_user_jwt
        response = self.client.post(
            self.report_create_url,
            headers=headers,
            data=json.dumps(self.report_form_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["_result"]["report_created"], True)

    def test_report_resolve_fail_guest_user(self):
        headers = copy.copy(self.guest_request_headers)
        response = self.client.post(
            self.report_resolve_url,
            headers=headers,
            data=json.dumps(self.resolve_report_form_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_report_resolve_fail_non_admin_user(self):
        headers = copy.copy(self.orcid_request_headers)
        self.client.cookies["jwt"] = self.orcid_user_jwt
        response = self.client.post(
            self.report_resolve_url,
            headers=headers,
            data=json.dumps(self.resolve_report_form_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_report_resolve_success_admin_user(self):
        headers = copy.copy(self.github_request_headers)
        self.client.cookies["jwt"] = self.github_user_jwt
        response = self.client.post(
            self.report_resolve_url,
            headers=headers,
            data=json.dumps(self.resolve_report_form_data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["_result"]["resolved"], True)
