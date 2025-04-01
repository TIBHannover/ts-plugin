from django.test import TestCase
from user_service.libs.test_config import BaseTest
from user_service.libs.test_helpers import TestHelper
import json
import uuid


class TestTermSetCreation(TestCase, BaseTest):
    @classmethod
    def setUpTestData(self) -> None:
        self.creation_url = "/term_set/create/"
        self.orcidUser, _ = TestHelper.createOrcidUser()
        self.gitHubUser, _ = TestHelper.createGitHubUser()
        term1 = {
            "iri": "http://purl.obolibrary.org/obo/OBI_0000070",
            "type": ["class"],
            "other_metadata": "something",
        }
        term2 = {
            "iri": "http://purl.obolibrary.org/obo/OBI_0000071",
            "type": ["property"],
            "other_metadata": "something",
        }
        term3 = {
            "iri": "http://purl.obolibrary.org/obo/OBI_0000072",
            "type": ["individual"],
            "other_metadata": "something",
        }
        self.term_set = {
            "id": str(uuid.uuid4()),
            "name": "test term set",
            "visibility": "public",
            "description": "some text",
            "terms": [term1, term2, term3],
        }

    def test_termset_creation_should_succeed(self):
        headers = self.github_request_headers
        res = self.client.post(
            self.creation_url,
            headers=headers,
            data=json.dumps(self.term_set),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual("test term set", res.json()["_result"]["term_set"]["name"])
