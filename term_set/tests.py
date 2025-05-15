from django.test import TestCase
from user_service.libs.test_config import BaseTest
from user_service.libs.test_helpers import TestHelper
import json
import uuid


class TestTermSetCreation(TestCase, BaseTest):
    @classmethod
    def setUpTestData(self) -> None:
        self.creation_url = "/term_set/create/"
        self.delete_url = "/term_set/delete/"
        self.update_url = "/term_set/update/"
        self.get_url = "/term_set/get/"
        self.orcidUser, _ = TestHelper.createOrcidUser()
        self.gitHubUser, _ = TestHelper.createGitHubUser()
        self.term1 = {
            "iri": "http://purl.obolibrary.org/obo/OBI_0000070",
            "type": ["class"],
            "other_metadata": "something",
        }
        self.term2 = {
            "iri": "http://purl.obolibrary.org/obo/OBI_0000071",
            "type": ["property"],
            "other_metadata": "something",
        }
        self.term3 = {
            "iri": "http://purl.obolibrary.org/obo/OBI_0000072",
            "type": ["individual"],
            "other_metadata": "something",
        }
        self.term_set = {
            "id": str(uuid.uuid4()),
            "name": "test term set",
            "visibility": "public",
            "description": "some text",
            "terms": [self.term1, self.term2, self.term3],
        }

        self.term_set_in_db = TestHelper.create_term_set(
            user=self.gitHubUser,
            name="termset_in_db",
            visibility="me",
            description="some text",
            terms=[self.term1, self.term2],
        )

        self.term_set_in_db_internal = TestHelper.create_term_set(
            user=self.gitHubUser,
            name="termset_in_db",
            visibility="internal",
            description="some text",
            terms=[self.term1, self.term2],
        )

        self.term_set_in_db_public = TestHelper.create_term_set(
            user=self.gitHubUser,
            name="termset_in_db",
            visibility="public",
            description="some text",
            terms=[self.term1, self.term2],
        )

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

    def test_termset_creation_should_fail_for_guest(self):
        headers = self.guest_request_headers
        res = self.client.post(
            self.creation_url,
            headers=headers,
            data=json.dumps(self.term_set),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 401)

    def test_termset_delete_should_succeed(self):
        headers = self.github_request_headers
        res = self.client.delete(
            self.delete_url + self.term_set_in_db["id"] + "/",
            headers=headers,
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(True, res.json()["_result"]["deleted"])

    def test_termset_delete_should_fail_for_non_owner(self):
        headers = self.orcid_request_headers
        res = self.client.delete(
            self.delete_url + self.term_set_in_db["id"] + "/",
            headers=headers,
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 404)
        # self.assertEqual("Terms set does not exist", res.content.decode())

    def test_termset_delete_should_fail_for_non_exisitng(self):
        headers = self.github_request_headers
        res = self.client.delete(
            self.delete_url + "some_uuid/",
            headers=headers,
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 404)
        # self.assertEqual("Terms set does not exist", res.content.decode())

    def test_termset_update_should_succeed(self):
        headers = self.github_request_headers
        self.term_set_in_db["name"] = "updated term set"
        self.term_set_in_db["terms"] = [self.term3]
        self.term_set_in_db["created_at"] = "some date ago"
        self.term_set_in_db["creator"] = None
        res = self.client.put(
            self.update_url,
            headers=headers,
            data=json.dumps(self.term_set_in_db),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual("updated term set", res.json()["_result"]["term_set"]["name"])
        self.assertEqual(1, len(res.json()["_result"]["term_set"]["terms"]))

    def test_termset_update_should_fail_for_non_owner(self):
        headers = self.orcid_request_headers
        self.term_set_in_db["name"] = "updated term set"
        self.term_set_in_db["terms"] = [self.term3]
        self.term_set_in_db["created_at"] = "some date ago"
        self.term_set_in_db["creator"] = None
        res = self.client.put(
            self.update_url,
            headers=headers,
            data=json.dumps(self.term_set_in_db),
            content_type="application/json",
        )
        print(res.content.decode())
        self.assertEqual(res.status_code, 404)
        # self.assertEqual(
        #     "Terms set does not exist",
        #     json.loads(res.content.decode())["_result"],
        # )

    def test_termset_get_public_one_should_succeed_for_guest(self):
        headers = self.guest_request_headers
        res = self.client.get(
            self.get_url + self.term_set_in_db_public["id"] + "/",
            headers=headers,
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
