from django.conf import settings
from user_service.libs.test_helpers import TestHelper
from django.test import TestCase


class BaseTest(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.test_ontology_id = "vibso"
        cls.test_parent_ontology_id = "bfo"
        cls.app_internal_base_url = ""
        cls.github_access_token = settings.GITHUB_TEST_ACCESS_TOKEN
        cls.orcid_access_token = settings.ORCID_TEST_ACCESS_TOKEN
        cls.orcid_id = settings.ORCID_LOGIN_USERNAME
        cls.test_github_username = "github_" + settings.GITHUB_LOGIN_USERNAME
        cls.test_orcid_username = "orcid_" + settings.ORCID_LOGIN_USERNAME
        cls.client_ts_id = "general"
        cls.orcidUser = TestHelper.createOrcidUser()
        cls.gitHubUser = TestHelper.createGitHubUser()
        cls.github_csrf_token = TestHelper.generate_csrf_token()
        cls.orcid_csrf_token = TestHelper.generate_csrf_token()
        cls.github_user_jwt = TestHelper.generate_jwt(
            {},
            cls.gitHubUser.username,
            cls.github_access_token,
            csrf_token=cls.github_csrf_token,
        )
        cls.orcid_user_jwt = TestHelper.generate_jwt(
            {},
            cls.orcidUser.username,
            cls.orcid_access_token,
            cls.orcid_id,
            csrf_token=cls.orcid_csrf_token,
        )

        cls.github_request_headers = {
            "Content-Type": "application/json",
            "X-TS-Auth-Provider": "github",
            "X-TS-Frontend-Id": cls.client_ts_id,
            "X-CSRF-Token": cls.github_csrf_token,
            "X-Auth-Token": cls.github_user_jwt,
        }

        cls.orcid_request_headers = {
            "Content-Type": "application/json",
            "X-TS-Auth-Provider": "orcid",
            "X-TS-Frontend-Id": cls.client_ts_id,
            "X-CSRF-Token": cls.orcid_csrf_token,
            "X-Auth-Token": cls.orcid_user_jwt,
        }

        cls.guest_request_headers = {
            "Authorization": "",
            "Content-Type": "application/json",
            "X-TS-Auth-Provider": "github",
            "X-TS-Frontend-Id": cls.client_ts_id,
            "X-Auth-Token": "invalid",
        }
