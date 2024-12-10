from logging import log
from django.test import TestCase
from user_service.libs.test_config import BaseTest
from django.conf import settings
from user.models import UserModel


class TestLogin(TestCase, BaseTest):

    @classmethod
    def setUpTestData(self) -> None:
        self.github_code = settings.GITHUB_LOGIN_CODE
        self.orcid_code = settings.ORCID_LOGIN_CODE            
        self.login_url = '/user/login/'
        self.validation_url = '/user/validate_login/'
        self.test_github_username = settings.GITHUB_LOGIN_USERNAME
        self.test_orcid_username = settings.ORCID_LOGIN_USERNAME
        self.client_ts_token = settings.FRONTEDN_AUTH_TOKEN


    def test_login_should_fail_without_auth_provider(self):
        headers = {
            "X-TS-Auth-APP-Code": self.github_code,            
            "X-TS-Frontend-Id": self.client_ts_id,
            "X-TS-Frontend-Token": self.client_ts_token
        }        

        login_response = self.client.get(self.login_url, headers=headers)        
        self.assertEqual(login_response.status_code, 403)
        self.assertIn("auth provider is not clear", login_response.content.decode())
    


    def test_login_should_fail_with_wrong_auth_provider(self):
        headers = {
            "X-TS-Auth-APP-Code": self.github_code,
            "X-TS-Auth-Provider": "some_provider",        
            "X-TS-Frontend-Id": self.client_ts_id,
            "X-TS-Frontend-Token": self.client_ts_token
        }

        login_response = self.client.get(self.login_url, headers=headers)
        self.assertEqual(login_response.status_code, 403)
        self.assertIn("auth provider is not clear", login_response.content.decode())
    


    def test_login_should_fail_without_client_ts_id(self):
        headers = {
            "X-TS-Auth-APP-Code": self.github_code,            
            "X-TS-Auth-Provider": "github",            
            "X-TS-Frontend-Token": self.client_ts_token
        }

        login_response = self.client.get(self.login_url, headers=headers)
        self.assertEqual(login_response.status_code, 401)
        self.assertIn("Client application is not allowed to use this service.", login_response.content.decode())
    


    def test_login_should_fail_without_client_ts_token(self):
        headers = {
            "X-TS-Auth-APP-Code": self.github_code,            
            "X-TS-Auth-Provider": "github",            
            "X-TS-Frontend-Id": self.client_ts_id            
        }

        login_response = self.client.get(self.login_url, headers=headers)
        self.assertEqual(login_response.status_code, 401)
        self.assertIn("Client application is not allowed to use this service.", login_response.content.decode())
    


    def test_login_should_fail_with_wrong_client_ts_id(self):
        headers = {
            "X-TS-Auth-APP-Code": self.github_code,            
            "X-TS-Auth-Provider": "github",
            "X-TS-Frontend-Id": "some_other_client_id",            
            "X-TS-Frontend-Token": self.client_ts_token
        }

        login_response = self.client.get(self.login_url, headers=headers)
        self.assertEqual(login_response.status_code, 401)
        self.assertIn("Client application is not allowed to use this service.", login_response.content.decode())
    


    def test_login_should_fail_with_wrong_client_ts_token(self):
        headers = {
            "X-TS-Auth-APP-Code": self.github_code,            
            "X-TS-Auth-Provider": "github",
            "X-TS-Frontend-Id": self.client_ts_id,            
            "X-TS-Frontend-Token": "some_token"
        }

        login_response = self.client.get(self.login_url, headers=headers)
        self.assertEqual(login_response.status_code, 401)
        self.assertIn("Client application is not allowed to use this service.", login_response.content.decode())
    
    
    
    def test_github_login_should_success(self):        
        headers = {
            "X-TS-Auth-APP-Code": self.github_code,
            "X-TS-Auth-Provider": "github",
            "X-TS-Frontend-Id": self.client_ts_id,
            "X-TS-Frontend-Token": self.client_ts_token
        }
        login_response = self.client.get(self.login_url, headers=headers)        
        self.assertEqual(login_response.status_code, 200)
        self.assertIsNot(login_response.json().get('_result').get('ts_username'), None)
    

    

    def test_github_user_registration_is_successful(self):
        '''
            This Test requires that the  test name "test_github_login_should_success" passes successfully.
        '''
        registered_username = "github_" + self.test_github_username
        db_user = UserModel.objects.filter(username=registered_username).first()
        self.assertIsNot(db_user, None)
        self.assertIsNot(db_user.id, None)
        self.assertEqual(db_user.username, registered_username)
    


    def test_github_user_registration_has_ts_internal_user_token(self):
        '''
            This Test requires that the  test name "test_github_login_should_success" passes successfully.
        '''
        registered_username = "github_" + self.test_github_username
        db_user = UserModel.objects.filter(username=registered_username).first()
        self.assertIsNot(db_user, None)
        self.assertIsNot(db_user.id, None)
        self.assertIsNot(db_user.user_ts_token, None)



    def test_orcid_login_should_success(self):        
        headers = {
            "X-TS-Auth-APP-Code": self.orcid_code,
            "X-TS-Auth-Provider": "orcid",
            "X-TS-Frontend-Id": self.client_ts_id,
            "X-TS-Frontend-Token": self.client_ts_token
        }
        login_response = self.client.get(self.login_url, headers=headers)        
        self.assertEqual(login_response.status_code, 200)
        self.assertIsNot(login_response.json().get('_result').get('ts_username'), None)




    def test_orcid_user_registration_is_successful(self):
        '''
            This Test requires that the last test name "test_orcid_login_should_success" passes successfully.
        '''
        registered_username = "orcid_" + self.test_orcid_username
        db_user = UserModel.objects.filter(username=registered_username).first()
        self.assertIsNot(db_user, None)
        self.assertIsNot(db_user.id, None)
        self.assertEqual(db_user.username, registered_username)



    def test_orcid_user_registration_has_ts_internal_user_token(self):
        '''
            This Test requires that the  test name "test_orcid_login_should_success" passes successfully.
        '''
        registered_username = "orcid_" + self.test_orcid_username
        db_user = UserModel.objects.filter(username=registered_username).first()
        self.assertIsNot(db_user, None)
        self.assertIsNot(db_user.id, None)
        self.assertIsNot(db_user.user_ts_token, None)

