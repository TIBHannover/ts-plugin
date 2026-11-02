import json
from unittest.mock import patch

from django.test import override_settings
from django.utils import timezone

from ontology_follow.models import OntologyFollowModel
from user.models import UserModel
from user_service.libs.test_config import BaseTest


@override_settings(DEBUG=False)
class OntologyFollowTests(BaseTest):
    url = "/ontology_follow/"

    def setUp(self):
        login = patch("user.libs.github.GithubLib.login_valid", return_value=True)
        login.start()
        self.addCleanup(login.stop)

    def request(self, method, payload=None, headers=None):
        return getattr(self.client, method)(
            self.url,
            data={} if method == "get" else json.dumps(payload) if payload is not None else "",
            content_type="application/json",
            headers=headers or self.github_request_headers,
        )

    def test_follow_normalizes_and_duplicate_follow_is_idempotent(self):
        for ontology_id in (" ViBsO ", "vibso"):
            response = self.request("post", {"ontology_id": ontology_id})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["_result"], {"ontology_id": "vibso", "following": True})
        self.assertEqual(OntologyFollowModel.objects.count(), 1)
        self.assertEqual(OntologyFollowModel.objects.get().user, self.gitHubUser)

    def test_list_only_returns_current_user_and_client_follows(self):
        other_client = UserModel.objects.create(
            username=self.gitHubUser.username, client_ts="nfdi4chem",
            auth_provider="github", created_at=timezone.now(),
        )
        for user, ontology_id in ((self.gitHubUser, "vibso"), (self.gitHubUser, "afo"),
                                  (self.orcidUser, "bfo"), (other_client, "chebi")):
            OntologyFollowModel.objects.create(user=user, ontology_id=ontology_id)
        response = self.request("get")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["_result"]["ontology_ids"], ["afo", "vibso"])
        response = self.request("get", headers={**self.github_request_headers, "X-TS-Frontend-Id": "nfdi4chem"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["_result"]["ontology_ids"], ["chebi"])

    def test_unfollow_physically_deletes_only_current_users_follow(self):
        self.request("post", {"ontology_id": "vibso"})
        other_follow = OntologyFollowModel.objects.create(user=self.orcidUser, ontology_id="vibso")
        for _ in range(2):
            response = self.request("delete", {"ontology_id": " VIBSO "})
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json()["_result"]["following"])
        self.assertEqual(list(OntologyFollowModel.objects.values_list("pk", flat=True)), [other_follow.pk])

    def test_invalid_ontology_ids_are_rejected_without_mutation(self):
        for payload in ({}, {"ontology_id": " "}, {"ontology_id": 1}, {"ontology_id": None}, []):
            for method in ("post", "delete"):
                with self.subTest(payload=payload, method=method):
                    self.assertEqual(self.request(method, payload).status_code, 400)
        self.assertFalse(OntologyFollowModel.objects.exists())

    def test_malformed_json_is_rejected(self):
        response = self.client.post(self.url, data="{", content_type="application/json", headers=self.github_request_headers)
        self.assertEqual(response.status_code, 400)

    def test_all_operations_require_authentication(self):
        for method in ("get", "post", "delete"):
            with self.subTest(method=method):
                self.assertEqual(self.request(method, {"ontology_id": "vibso"}, self.guest_request_headers).status_code, 401)
        self.assertFalse(OntologyFollowModel.objects.exists())
