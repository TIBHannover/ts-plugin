from django.test import TestCase
from user_service.libs.test_config import BaseTest
import copy
from user_service.libs.test_helpers import TestHelper


class TestAuthValidation(TestCase, BaseTest):
    @classmethod
    def setUpTestData(self) -> None:
        self.auth_validation_url = "/user/validate_login/"
        self.gitHubUser = TestHelper.createGitHubUser()
        self.orcidUser = TestHelper.createOrcidUser()
        self.github_user_jwt = TestHelper.generate_jwt(
            {}, self.gitHubUser.username, self.github_access_token
        )
        self.orcid_user_jwt = TestHelper.generate_jwt(
            {},
            self.orcidUser.username,
            self.orcid_access_token,
            self.orcid_id,
        )

    def test_login_validation_should_fail_without_auth_provider(self):
        headers = copy.copy(self.github_request_headers)
        del headers["X-TS-Auth-Provider"]
        self.client.cookies["jwt"] = self.github_user_jwt
        validation_response = self.client.get(self.auth_validation_url, headers=headers)
        self.assertEqual(validation_response.status_code, 401)
        self.assertIn(
            "auth provider is not clear", validation_response.content.decode()
        )

    def test_login_validation_should_success_github(self):
        headers = copy.copy(self.github_request_headers)
        self.client.cookies["jwt"] = self.github_user_jwt
        validation_response = self.client.get(self.auth_validation_url, headers=headers)
        self.assertEqual(validation_response.status_code, 200)
        self.assertEqual(validation_response.json().get("_result").get("valid"), True)

    def test_login_validation_should_success_orcid(self):
        headers = copy.copy(self.orcid_request_headers)
        self.client.cookies["jwt"] = self.orcid_user_jwt
        validation_response = self.client.get(self.auth_validation_url, headers=headers)
        self.assertEqual(validation_response.status_code, 200)
        self.assertEqual(validation_response.json().get("_result").get("valid"), True)
