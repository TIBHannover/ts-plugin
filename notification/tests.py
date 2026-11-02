from types import SimpleNamespace
from unittest.mock import patch

from django.db import transaction
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from github.models import GithubIssueRequestModel
from note.models import NoteModel
from notification.services import ontology_update_link
from ontology_follow.models import OntologyFollowModel
from pub_link.models import PubLinkModel
from user.models import EmailLog, UserModel


@override_settings(
    DEFAULT_FROM_EMAIL="notifications@example.org",
    GENERAL_FRONTEND_REDIRECT_URL="https://general.example/ts/",
    NFDI4CHEM_FRONTEND_REDIRECT_URL="https://terminology.nfdi4chem.de/ts/",
)
class OntologyNotificationTests(TestCase):
    def setUp(self):
        self.creator = self.make_user("creator")
        self.follower = self.make_user("follower", email="follower@example.org")
        self.follow(self.follower)
        queue = patch("user_service.libs.email.send_notification_email.delay")
        self.delay = queue.start()
        self.addCleanup(queue.stop)

    def make_user(self, username, **kwargs):
        return UserModel.objects.create(
            username=username, created_at=timezone.now(), auth_provider="github",
            **{"client_ts": "general", **kwargs},
        )

    def follow(self, user, ontology_id="vibso"):
        return OntologyFollowModel.objects.create(user=user, ontology_id=ontology_id)

    def create_content(self, event, creator=None, **kwargs):
        creator = creator or self.creator
        fields = {"ontology_id": " ViBsO ", "created_at": timezone.now(), **kwargs}
        if event == "note":
            return NoteModel.objects.create(
                creator=creator, title="New note", content="Note content",
                semantic_component_type="ontology", semantic_component_iri="",
                **{"visibility": "public", **fields},
            )
        if event == "publication":
            return PubLinkModel.objects.create(
                creator=creator, doi="10.1234/example", citation="Example publication", **fields,
            )
        return GithubIssueRequestModel.objects.create(
            user=creator, issue_title="New issue", issue_content="Issue content",
            issue_url="https://github.com/example/ontology/issues/1",
            **{"client_ts": creator.client_ts, "issue_type": "general", **fields},
        )

    def test_all_content_types_only_notify_eligible_followers_in_same_client(self):
        self.follow(self.make_user("follower", client_ts="nfdi4chem", email="other-client@example.org"))
        self.follow(self.make_user("inactive", is_active=False, email="inactive@example.org"))
        self.follow(self.make_user("blocked", is_blocked=True, email="blocked@example.org"))
        self.follow(self.make_user("no-email"))
        self.follow(self.make_user("other-ontology", email="other-ontology@example.org"), "afo")
        self.make_user("not-following", email="not-following@example.org")
        for event in ("note", "publication", "issue"):
            with self.subTest(event=event):
                EmailLog.objects.all().delete()
                self.delay.reset_mock()
                with self.captureOnCommitCallbacks(execute=True):
                    content = self.create_content(event)
                    self.assertFalse(EmailLog.objects.exists())
                    self.delay.assert_not_called()
                log = EmailLog.objects.get()
                self.assertEqual(log.recipient, self.follower.email)
                self.assertEqual(log.client_ts, "general")
                self.assertEqual(log.notification_type, f"ontology_{event}")
                self.assertEqual(log.reference, f"{event}:{content.pk}")
                self.delay.assert_called_once()
                self.assertEqual(self.delay.call_args.args[0], log.pk)

    def test_same_username_in_other_client_receives_only_its_own_clients_updates(self):
        creator = self.make_user("creator", client_ts="nfdi4chem")
        follower = self.make_user("follower", client_ts="nfdi4chem", email="chem@example.org")
        self.follow(follower)
        for event in ("note", "publication", "issue"):
            with self.subTest(event=event):
                EmailLog.objects.all().delete()
                with self.captureOnCommitCallbacks(execute=True):
                    self.create_content(event, creator=creator)
                log = EmailLog.objects.get()
                self.assertEqual(log.recipient, "chem@example.org")
                self.assertEqual(log.client_ts, "nfdi4chem")

    def test_private_notes_never_notify_even_their_owner(self):
        self.creator.email = "owner@example.org"
        self.creator.save()
        self.follow(self.creator)
        with self.captureOnCommitCallbacks(execute=True):
            self.create_content("note", visibility="me")
        self.assertFalse(EmailLog.objects.exists())
        self.delay.assert_not_called()

    def test_inactive_notes_never_notify(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.create_content("note", active=False)
        self.assertFalse(EmailLog.objects.exists())
        self.delay.assert_not_called()

    def test_internal_notes_notify_followers(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.create_content("note", visibility="internal")
        self.assertEqual(EmailLog.objects.get().recipient, self.follower.email)

    def test_unfollow_prevents_notifications(self):
        self.follower.ontology_follows.all().delete()
        with self.captureOnCommitCallbacks(execute=True):
            for event in ("note", "publication", "issue"):
                self.create_content(event)
        self.assertFalse(EmailLog.objects.exists())
        self.delay.assert_not_called()

    def test_updates_do_not_notify(self):
        for event in ("note", "publication", "issue"):
            with self.subTest(event=event):
                with self.captureOnCommitCallbacks(execute=True):
                    content = self.create_content(event)
                EmailLog.objects.all().delete()
                self.delay.reset_mock()
                with self.captureOnCommitCallbacks(execute=True):
                    content.ontology_id = "vibso"
                    content.save()
                self.assertFalse(EmailLog.objects.exists())
                self.delay.assert_not_called()

    def test_rolled_back_content_never_notifies(self):
        for event in ("note", "publication", "issue"):
            with self.subTest(event=event):
                with self.captureOnCommitCallbacks(execute=True):
                    with self.assertRaises(ValueError), transaction.atomic():
                        content = self.create_content(event)
                        raise ValueError("Rollback content")
                self.assertFalse(type(content).objects.filter(pk=content.pk).exists())
        self.assertFalse(EmailLog.objects.exists())
        self.delay.assert_not_called()

    def test_term_requests_also_notify(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.create_content("issue", issue_type="termRequest")
        self.assertEqual(EmailLog.objects.get().notification_type, "ontology_issue")

    def test_issue_with_conflicting_client_does_not_notify(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.create_content("issue", client_ts="nfdi4chem")
        self.assertFalse(EmailLog.objects.exists())
        self.delay.assert_not_called()

    def test_note_and_publication_emails_include_client_frontend_links(self):
        creator = self.make_user("chem-creator", client_ts="nfdi4chem")
        follower = self.make_user("chem-follower", client_ts="nfdi4chem", email="chem@example.org")
        self.follow(follower, "afo")
        for event, page in (("note", "notes"), ("publication", "publications")):
            with self.subTest(event=event):
                self.delay.reset_mock()
                with self.captureOnCommitCallbacks(execute=True):
                    content = self.create_content(event, creator=creator, ontology_id="afo")
                expected = f"https://terminology.nfdi4chem.de/ts/ontologies/afo/{page}"
                if event == "note":
                    expected += f"?noteId={content.pk}"
                self.delay.assert_called_once()
                self.assertIn(expected, self.delay.call_args.args[1])


class OntologyUpdateLinkTests(SimpleTestCase):
    def test_base_url_with_or_without_trailing_slash_preserves_ts_and_encodes_ontology(self):
        content = SimpleNamespace(ontology_id=" AFO/Space Name? ", pk=42)
        for client_ts in ("general", "nfdi4chem", "nfdi4ing"):
            for base in ("https://example.org/ts", "https://example.org/ts/"):
                with self.subTest(client_ts=client_ts, base=base), override_settings(**{f"{client_ts.upper()}_FRONTEND_REDIRECT_URL": base}):
                    self.assertEqual(
                        ontology_update_link(content, "note", client_ts),
                        "https://example.org/ts/ontologies/afo%2Fspace%20name%3F/notes?noteId=42",
                    )
                    self.assertEqual(
                        ontology_update_link(content, "publication", client_ts),
                        "https://example.org/ts/ontologies/afo%2Fspace%20name%3F/publications",
                    )

    @override_settings(GENERAL_FRONTEND_REDIRECT_URL=None)
    def test_missing_redirect_url_has_no_link(self):
        self.assertEqual(ontology_update_link(SimpleNamespace(ontology_id="afo", pk=1), "note", "general"), "")
