from user_service.libs.test_config import BaseTest
from user_service.libs.test_helpers import TestHelper
import random
import string
import copy
import json
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from user_service.libs.safe_http import SafeRequestError


class TestOntologySuggestion(BaseTest):
    @classmethod
    def setUpTestData(self) -> None:
        super().setUpTestData()
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

    def test_adopter_request_should_success(self):
        headers = copy.copy(self.github_request_headers)

        adopter_request = {
            "email": "me@me",
            "username": "me",
            "name": "test_ontology",
            "purl": "https://purl.obolibrary.org/obo/sepio.owl",
            "adopter_type": "project",
            "adopter_name": "Test Adopter",
            "adopter_alt_name": "",
            "adopter_pid": "",
            "adopter_homepage": "",
            "provider_name": "",
            "provider_pid": "",
            "usage_description": "Testing ontology adoption",
            "usage_channel": "API",
        }

        url = "/ontologysuggestion/adopter_create/"

        self.client.cookies["jwt"] = self.github_user_jwt

        response = self.client.post(
            url,
            headers=headers,
            data=json.dumps(adopter_request),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)


class TestPurlValidator(SimpleTestCase):
    @patch("ontology_suggestion.views.safe_head")
    def test_valid_purl(self, safe_head):
        safe_head.return_value = MagicMock(
            status_code=200, headers={"Content-Type": "text/turtle"}
        )

        response = self.client.get(
            "/ontologysuggestion/purl_is_valid/",
            {"purl": "https://example.org/ontology.ttl"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["_result"], {"valid": True})
        safe_head.assert_called_once_with("https://example.org/ontology.ttl")

    @patch("ontology_suggestion.views.safe_head")
    def test_invalid_purls_are_rejected(self, safe_head):
        safe_head.side_effect = SafeRequestError("URL could not be fetched")

        for purl in (
            "http://example.org/ontology.ttl",
            "https://127.0.0.1/ontology.ttl",
            "https://[::1]/ontology.ttl",
            "not-a-url",
        ):
            with self.subTest(purl=purl):
                response = self.client.get(
                    "/ontologysuggestion/purl_is_valid/", {"purl": purl}
                )

                self.assertEqual(
                    response.json()["_result"],
                    {
                        "valid": False,
                        "reason": "PURL is not a resolvable URL",
                    },
                )

    @patch("ontology_suggestion.views.safe_head")
    def test_purl_with_invalid_status_or_content_type_is_rejected(self, safe_head):
        for result in (
            MagicMock(status_code=404, headers={"Content-Type": "text/turtle"}),
            MagicMock(
                status_code=200, headers={"Content-Type": "application/pdf"}
            ),
        ):
            safe_head.return_value = result
            response = self.client.get(
                "/ontologysuggestion/purl_is_valid/",
                {"purl": "https://example.org/ontology.owl"},
            )

            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json()["_result"]["valid"])
