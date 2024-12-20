from django.test import TestCase
from user_service.libs.test_config import BaseTest
from user_service.libs.test_helpers import TestHelper
import copy
import json
from github.models import GithubIssueRequestModel
from datetime import datetime as _time



class TestTermRequest(TestCase, BaseTest):

    @classmethod
    def setUpTestData(self) -> None:
        self.term_request_data = {
            "title": "test issue",
            "content": "test content",
            "repo_url": "https://github.com/TIBHannover/rsc-cmo",
            "ontology_id": "vibso",
            "issueType": "termRequest",
        }
        self.term_request_url = "/github/submit_issue/"
        self.github_user, _ = TestHelper.createGitHubUser()
        TestHelper.createOrcidUser()




    def test_term_request_should_fail_without_issue_title(self):
        post_data = copy.copy(self.term_request_data)
        del post_data["title"]
        headers = self.github_request_headers
        response = self.client.post(self.term_request_url, headers=headers, data=json.dumps(post_data), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("Mandatory Fields are missing", response.content.decode())



    def test_term_request_should_fail_without_issue_content(self):
        post_data = copy.copy(self.term_request_data)
        del post_data["content"]
        headers = self.github_request_headers
        response = self.client.post(self.term_request_url, headers=headers, data=json.dumps(post_data), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("Mandatory Fields are missing", response.content.decode())



    def test_term_request_should_fail_without_issue_tracker_url(self):
        post_data = copy.copy(self.term_request_data)
        del post_data["repo_url"]
        headers = self.github_request_headers
        response = self.client.post(self.term_request_url, headers=headers, data=json.dumps(post_data), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("Mandatory Fields are missing", response.content.decode())



    def test_term_request_should_fail_without_ontology_id(self):
        post_data = copy.copy(self.term_request_data)
        del post_data["ontology_id"]
        headers = self.github_request_headers
        response = self.client.post(self.term_request_url, headers=headers, data=json.dumps(post_data), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("Mandatory Fields are missing", response.content.decode())



    def test_term_request_should_fail_without_issue_type(self):
        post_data = copy.copy(self.term_request_data)
        del post_data["issueType"]
        headers = self.github_request_headers
        response = self.client.post(self.term_request_url, headers=headers, data=json.dumps(post_data), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("Mandatory Fields are missing", response.content.decode())



    def test_term_request_should_fail_when_ontology_is_not_hosted_on_github(self):
        post_data = copy.copy(self.term_request_data)
        post_data["repo_url"] = "https://www.some_other_system.com/issues"
        headers = self.github_request_headers
        response = self.client.post(self.term_request_url, headers=headers, data=json.dumps(post_data), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("Ontology is not hosted on Github", response.content.decode())


    def test_term_request_should_fail_for_orcid_user(self):
        post_data = copy.copy(self.term_request_data)
        headers = self.orcid_request_headers
        response = self.client.post(self.term_request_url, headers=headers, data=json.dumps(post_data), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertIn("Only github users can use this feature", response.json()["_result"]["error"])



    def test_term_request_should_success(self):
        post_data = copy.copy(self.term_request_data)
        headers = self.github_request_headers
        response = self.client.post(self.term_request_url, headers=headers, data=json.dumps(post_data), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertIsNot(response.json()["_result"]["new_issue_url"], False)



    def test_term_request_list_should_success(self):
        github_issue_db_entry = {
            "user": self.github_user,
            "created_at": _time.now(),
            "ontology_id": self.test_ontology_id,
            "issue_content": "test content",
            "issue_title": "test issue",
            "issue_url": "http://",
            "client_ts": 'general',
            "issue_type": "termRequest"
        }
        github_issue_record = GithubIssueRequestModel(**github_issue_db_entry)
        github_issue_record.save()

        response = self.client.get("/github/get_submited_issues/", headers=self.github_request_headers)
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.json()["_result"]["submited_issues"]), 0)
        self.assertEqual(response.json()["_result"]["submited_issues"][0]["ontology_id"], "vibso")
