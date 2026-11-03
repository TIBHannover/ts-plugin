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

    def test_follow_defaults_all_preferences_to_enabled(self):
        self.assertEqual(self.request("post", {"ontology_id": "vibso"}).status_code, 200)
        self.assertEqual(self.request("get").json()["_result"]["follows"], [{
            "ontology_id": "vibso", "notify_note": True,
            "notify_issue": True, "notify_publication": True, "notify_github": True,
        }])

    def test_each_preference_can_be_created_disabled_and_updated_independently(self):
        for field in ("notify_note", "notify_issue", "notify_publication"):
            with self.subTest(field=field):
                OntologyFollowModel.objects.all().delete()
                self.assertEqual(self.request("post", {"ontology_id": "vibso", field: False}).status_code, 200)
                follow = OntologyFollowModel.objects.get()
                self.assertFalse(getattr(follow, field))
                for other in {"notify_note", "notify_issue", "notify_publication"} - {field}:
                    self.assertTrue(getattr(follow, other))
                self.request("post", {"ontology_id": "vibso"})
                follow.refresh_from_db()
                self.assertFalse(getattr(follow, field))
                self.assertEqual(self.request("post", {"ontology_id": " VIBSO ", field: True}).status_code, 200)
                follow.refresh_from_db()
                self.assertTrue(getattr(follow, field))
                self.assertEqual(OntologyFollowModel.objects.count(), 1)

    def test_all_disabled_preferences_are_saved_and_returned(self):
        payload = {"ontology_id": "vibso", "notify_note": False,
                   "notify_issue": False, "notify_publication": False, "notify_github": False}
        self.assertEqual(self.request("post", payload).status_code, 200)
        self.assertEqual(self.request("get").json()["_result"], {
            "ontology_ids": ["vibso"], "follows": [payload],
        })

    def test_invalid_preferences_never_create_or_partially_update_a_follow(self):
        for field in ("notify_note", "notify_issue", "notify_publication"):
            for value in (None, "false", 0, 1, [], {}):
                for existing in (False, True):
                    with self.subTest(field=field, value=value, existing=existing):
                        OntologyFollowModel.objects.all().delete()
                        if existing:
                            OntologyFollowModel.objects.create(user=self.gitHubUser, ontology_id="vibso")
                        payload = {"ontology_id": "vibso", "notify_note": False, field: value}
                        self.assertEqual(self.request("post", payload).status_code, 400)
                        self.assertEqual(OntologyFollowModel.objects.count(), int(existing))
                        if existing:
                            follow = OntologyFollowModel.objects.get()
                            self.assertTrue(follow.notify_note)
                            self.assertTrue(follow.notify_issue)
                            self.assertTrue(follow.notify_publication)
                            self.assertEqual(self.request("patch", payload).status_code, 400)
                            follow.refresh_from_db()
                            self.assertTrue(follow.notify_note)
                            self.assertTrue(follow.notify_issue)
                            self.assertTrue(follow.notify_publication)

    def test_preference_updates_are_scoped_to_current_user_and_client(self):
        other_client = UserModel.objects.create(
            username=self.gitHubUser.username, client_ts="nfdi4chem",
            auth_provider="github", created_at=timezone.now(),
        )
        for user in (self.gitHubUser, self.orcidUser, other_client):
            OntologyFollowModel.objects.create(user=user, ontology_id="vibso")
        self.assertEqual(self.request("post", {"ontology_id": "vibso", "notify_note": False}).status_code, 200)
        self.assertFalse(self.gitHubUser.ontology_follows.get().notify_note)
        self.assertTrue(self.orcidUser.ontology_follows.get().notify_note)
        self.assertTrue(other_client.ontology_follows.get().notify_note)
        self.assertEqual(self.request("post", {"ontology_id": "vibso", "notify_issue": False}, {
            **self.github_request_headers, "X-TS-Frontend-Id": "nfdi4chem",
        }).status_code, 200)
        self.assertFalse(other_client.ontology_follows.get().notify_issue)
        self.assertTrue(self.gitHubUser.ontology_follows.get().notify_issue)

    def test_patch_updates_existing_follow_and_preserves_other_preferences(self):
        follow = OntologyFollowModel.objects.create(
            user=self.gitHubUser, ontology_id="vibso", notify_issue=False,
        )
        response = self.request("patch", {"ontology_id": " VIBSO ", "notify_note": False})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["_result"], {"ontology_id": "vibso", "following": True})
        follow.refresh_from_db()
        self.assertFalse(follow.notify_note)
        self.assertFalse(follow.notify_issue)
        self.assertTrue(follow.notify_publication)
        self.assertEqual(OntologyFollowModel.objects.count(), 1)

    def test_patch_requires_existing_own_follow_and_preferences(self):
        other_client = UserModel.objects.create(
            username=self.gitHubUser.username, client_ts="nfdi4chem",
            auth_provider="github", created_at=timezone.now(),
        )
        for user, ontology_id in ((self.orcidUser, "afo"), (other_client, "chebi"),
                                  (self.gitHubUser, "vibso")):
            OntologyFollowModel.objects.create(user=user, ontology_id=ontology_id)
        for payload in ({"ontology_id": "missing", "notify_note": False},
                        {"ontology_id": "afo", "notify_note": False},
                        {"ontology_id": "chebi", "notify_note": False},
                        {"ontology_id": "vibso"}):
            with self.subTest(payload=payload):
                self.assertEqual(self.request("patch", payload).status_code, 400)
        self.assertEqual(OntologyFollowModel.objects.count(), 3)
        self.assertFalse(OntologyFollowModel.objects.filter(notify_note=False).exists())

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
            for method in ("post", "patch", "delete"):
                with self.subTest(payload=payload, method=method):
                    self.assertEqual(self.request(method, payload).status_code, 400)
        self.assertFalse(OntologyFollowModel.objects.exists())

    def test_malformed_json_is_rejected(self):
        response = self.client.post(self.url, data="{", content_type="application/json", headers=self.github_request_headers)
        self.assertEqual(response.status_code, 400)

    def test_all_operations_require_authentication(self):
        for method in ("get", "post", "patch", "delete"):
            with self.subTest(method=method):
                self.assertEqual(self.request(method, {"ontology_id": "vibso"}, self.guest_request_headers).status_code, 401)
        self.assertFalse(OntologyFollowModel.objects.exists())
