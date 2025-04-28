from django.test import TestCase
from user_service.libs.test_config import BaseTest
from user_service.libs.test_helpers import TestHelper
import random
import string
import copy
import json


class TestOntologySuggestion(TestCase, BaseTest):
    @classmethod
    def setUpTestData(self) -> None:
        self.ontology_suggestion = {
            "email": "me@me",
            "username": "me",
            "reason": "reason",
            "name": "".join(
                random.choices(string.ascii_letters + string.digits, k=10)
            ),  # we use a random string as the ontology's name for sake of testing.
            "purl": "https://purl.obolibrary.org/obo/sepio.owl",
            "collection_ids": "x,y",
            "collection_suggestion": "",
        }
        TestHelper.createGitHubUser()

    def test_onto_suggest_should_success(self):
        headers = copy.copy(self.github_request_headers)
        url = "/ontologysuggestion/create/"
        response = self.client.post(
            url,
            headers=headers,
            data=json.dumps(self.ontology_suggestion),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["_result"]["respone"], "ontology is suggested successfully"
        )

    def test_onto_suggest_should_fail_for_existing_suggestion(self):
        """repeating the last test should fail since it already exists"""
        headers = copy.copy(self.github_request_headers)
        url = "/ontologysuggestion/create/"
        response = self.client.post(
            url,
            headers=headers,
            data=json.dumps(self.ontology_suggestion),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("suggestion exists.", response.content.decode())

    def test_onto_suggest_should_success_for_collection(self):
        headers = copy.copy(self.github_request_headers)
        url = "/ontologysuggestion/create/"
        self.ontology_suggestion["collection_suggestion"] = "true"
        response = self.client.post(
            url,
            headers=headers,
            data=json.dumps(self.ontology_suggestion),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["_result"]["response"], "ontology is suggested successfully"
        )
