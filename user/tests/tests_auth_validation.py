from user_service.libs.test_config import BaseTest
import copy
from user_service.libs.test_helpers import TestHelper


class TestAuthValidation(BaseTest):
    @classmethod
    def setUpTestData(self) -> None:
        super().setUpTestData()
        self.auth_validation_url = "/user/validate_login/"

    def test_login_validation_should_fail_without_auth_provider(self):
        headers = copy.copy(self.github_request_headers)
        del headers["X-TS-Auth-Provider"]
        validation_response = self.client.get(self.auth_validation_url, headers=headers)
        self.assertEqual(validation_response.status_code, 401)
        self.assertIn(
            "auth provider is not clear", validation_response.content.decode()
        )

    def test_login_validation_should_success_github(self):
        headers = copy.copy(self.github_request_headers)
        validation_response = self.client.get(self.auth_validation_url, headers=headers)
        self.assertEqual(validation_response.status_code, 200)
        self.assertEqual(validation_response.json().get("_result").get("valid"), True)

    def test_login_validation_should_success_orcid(self):
        headers = copy.copy(self.orcid_request_headers)
        validation_response = self.client.get(self.auth_validation_url, headers=headers)
        self.assertEqual(validation_response.status_code, 200)
        self.assertEqual(validation_response.json().get("_result").get("valid"), True)
