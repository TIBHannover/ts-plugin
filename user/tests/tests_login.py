from user_service.libs.test_config import BaseTest
from django.conf import settings
from user.models import UserModel
from user_service.libs.test_helpers import TestHelper
from unittest.mock import patch
from django.test import override_settings
import datetime


@override_settings(
    AUTH_COOKIE_PARTITIONED_ORIGINS=["frontend.test"],
    FRONTEDN_AUTH_TOKEN="test-frontend-token",
)
class TestLogin(BaseTest):

    @classmethod
    def setUpTestData(self) -> None:
        super().setUpTestData()
        self.github_code = settings.GITHUB_LOGIN_CODE
        self.orcid_code = settings.ORCID_LOGIN_CODE
        self.login_url = "/user/login/"
        self.validation_url = "/user/validate_login/"
        self.test_github_username = settings.GITHUB_LOGIN_USERNAME
        self.test_orcid_username = settings.ORCID_LOGIN_USERNAME
        self.client_ts_token = settings.FRONTEDN_AUTH_TOKEN

    def test_login_should_fail_without_auth_provider(self):
        headers = {
            "X-TS-Auth-APP-Code": self.github_code,
            "X-TS-Frontend-Id": self.client_ts_id,
            "X-TS-Frontend-Token": self.client_ts_token,
        }

        login_response = self.client.get(self.login_url, headers=headers)
        self.assertEqual(login_response.status_code, 401)
        self.assertIn("auth provider is not clear", login_response.content.decode())

    def test_login_should_fail_with_wrong_auth_provider(self):
        headers = {
            "X-TS-Auth-APP-Code": self.github_code,
            "X-TS-Auth-Provider": "some_provider",
            "X-TS-Frontend-Id": self.client_ts_id,
            "X-TS-Frontend-Token": self.client_ts_token,
        }

        login_response = self.client.get(self.login_url, headers=headers)
        self.assertEqual(login_response.status_code, 401)
        self.assertIn("auth provider is not clear", login_response.content.decode())

    def test_login_should_fail_without_client_ts_id(self):
        headers = {
            "X-TS-Auth-APP-Code": self.github_code,
            "X-TS-Auth-Provider": "github",
            "X-TS-Frontend-Token": self.client_ts_token,
        }

        login_response = self.client.get(self.login_url, headers=headers)
        self.assertEqual(login_response.status_code, 401)
        self.assertIn(
            "Client application is not allowed to use this service.",
            login_response.content.decode(),
        )

    def test_login_should_fail_without_client_ts_token(self):
        headers = {
            "X-TS-Auth-APP-Code": self.github_code,
            "X-TS-Auth-Provider": "github",
            "X-TS-Frontend-Id": self.client_ts_id,
        }

        login_response = self.client.get(self.login_url, headers=headers)
        self.assertEqual(login_response.status_code, 401)
        self.assertIn(
            "Client application is not allowed to use this service.",
            login_response.content.decode(),
        )

    def test_login_should_fail_with_wrong_client_ts_id(self):
        headers = {
            "X-TS-Auth-APP-Code": self.github_code,
            "X-TS-Auth-Provider": "github",
            "X-TS-Frontend-Id": "some_other_client_id",
            "X-TS-Frontend-Token": self.client_ts_token,
        }

        login_response = self.client.get(self.login_url, headers=headers)
        self.assertEqual(login_response.status_code, 401)
        self.assertIn(
            "Client application is not allowed to use this service.",
            login_response.content.decode(),
        )

    def test_login_should_fail_with_wrong_client_ts_token(self):
        headers = {
            "X-TS-Auth-APP-Code": self.github_code,
            "X-TS-Auth-Provider": "github",
            "X-TS-Frontend-Id": self.client_ts_id,
            "X-TS-Frontend-Token": "some_token",
        }

        login_response = self.client.get(self.login_url, headers=headers)
        self.assertEqual(login_response.status_code, 401)
        self.assertIn(
            "Client application is not allowed to use this service.",
            login_response.content.decode(),
        )

    @patch("user.libs.auth.GithubLib.authenticate")
    def test_github_login_should_success(self, mock_authenticate):
        mock_authenticate.return_value = {
            "ts_username": self.gitHubUser.username,
            "name": self.gitHubUser.name,
            "token": self.github_access_token,
            "company": "TIB",
            "github_home": "https://github.com/test",
        }
        headers = {
            "X-TS-Auth-APP-Code": self.github_code,
            "X-TS-Auth-Provider": "github",
            "X-TS-Frontend-Id": self.client_ts_id,
            "X-TS-Frontend-Token": self.client_ts_token,
            "Origin": "https://frontend.test",
        }
        login_response = self.client.get(self.login_url, headers=headers)
        self.assertEqual(login_response.status_code, 200)
        result = login_response.json().get("_result")
        self.assertNotIn("jwt", result)
        self.assertNotIn("token", result)
        self.assertIn("csrf_token", result)
        jwt_cookie = login_response.cookies.get("jwt")
        self.assertIsNotNone(jwt_cookie)
        self.assertTrue(jwt_cookie["httponly"])
        self.assertTrue(jwt_cookie["secure"])
        self.assertEqual(jwt_cookie["samesite"], "None")
        self.assertTrue(jwt_cookie["partitioned"])
        jwt_token = jwt_cookie.value
        created_user_data = TestHelper.validate_and_return_jwt_payload(jwt_token)
        self.assertNotEqual(created_user_data, {})
        self.assertEqual(created_user_data.get("csrf"), result["csrf_token"])
        expected_exp = datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=7)
        jwt_exp = datetime.datetime.fromtimestamp(
            created_user_data["exp"], datetime.UTC
        )
        cookie_exp = datetime.datetime.strptime(
            jwt_cookie["expires"], "%a, %d %b %Y %H:%M:%S GMT"
        ).replace(tzinfo=datetime.UTC)
        self.assertLess(abs((jwt_exp - expected_exp).total_seconds()), 10)
        self.assertLess(abs((cookie_exp - expected_exp).total_seconds()), 10)
        self.assertIsNot(created_user_data.get("ts_username"), None)
        db_user = UserModel.objects.filter(
            username=created_user_data["ts_username"]
        ).first()
        self.assertIsNot(db_user, None)
        self.assertIsNot(db_user.id, None)

    # def test_orcid_login_should_success(self):
    #     headers = {
    #         "X-TS-Auth-APP-Code": self.orcid_code,
    #         "X-TS-Auth-Provider": "orcid",
    #         "X-TS-Frontend-Id": self.client_ts_id,
    #         "X-TS-Frontend-Token": self.client_ts_token
    #     }
    #     login_response = self.client.get(self.login_url, headers=headers)
    #     created_user_data = login_response.json().get('_result')
    #     self.assertEqual(login_response.status_code, 200)
    #     self.assertIsNot(created_user_data.get('ts_username'), None)
    #     db_user = UserModel.objects.filter(username=created_user_data['ts_username']).first()
    #     self.assertIsNot(db_user, None)
    #     self.assertIsNot(db_user.id, None)
    #     self.assertIsNot(db_user.user_ts_token, None)
