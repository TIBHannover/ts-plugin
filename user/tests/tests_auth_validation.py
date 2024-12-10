from django.test import TestCase
from user_service.libs.test_config import BaseTest
import copy
from user_service.libs.test_helpers import TestHelper


class TestAuthValidation(TestCase, BaseTest):

    @classmethod
    def setUpTestData(self) -> None:
        self.auth_validation_url = '/user/validate_login/'
        TestHelper.createGitHubUser()
        TestHelper.createOrcidUser()


    def test_login_validation_should_fail_without_auth_provider(self):
        headers = copy.copy(self.github_request_headers)
        del headers['X-TS-Auth-Provider']
        validation_response = self.client.get(self.auth_validation_url, headers=headers)        
        self.assertEqual(validation_response.status_code, 401)
        self.assertIn("auth provider is not clear", validation_response.content.decode())
    


    def test_login_validation_should_fail_with_wrong_github_token(self):        
        headers = copy.copy(self.github_request_headers)
        headers['Authorization'] = "some_token"        
        validation_response = self.client.get(self.auth_validation_url, headers=headers)                
        self.assertEqual(validation_response.status_code, 401)
        self.assertIn("Not Authorized", validation_response.content.decode())



    def test_login_validation_should_fail_with_wrong_orcid_token(self):        
        headers = copy.copy(self.orcid_request_headers)
        headers['Authorization'] = "some_token"   
        validation_response = self.client.get(self.auth_validation_url, headers=headers)           
        self.assertEqual(validation_response.status_code, 401)
        self.assertIn("Not Authorized", validation_response.content.decode())




    def test_login_validation_should_fail_with_wrong_orcid_id(self):    
        headers = copy.copy(self.orcid_request_headers)
        del headers['X-TS-Orcid-Id']
        validation_response = self.client.get(self.auth_validation_url, headers=headers)            
        self.assertEqual(validation_response.status_code, 401)
        self.assertIn("Not Authorized", validation_response.content.decode())



    def test_login_validation_should_fail_with_wrong_client_ts(self):
        headers = copy.copy(self.github_request_headers)
        del headers['X-TS-Frontend-Token']
        validation_response = self.client.get(self.auth_validation_url, headers=headers)        
        self.assertEqual(validation_response.status_code, 401)
        self.assertIn("Client application is not allowed to use this service.", validation_response.content.decode())



    def test_login_validation_should_fail_with_wrong_ts_username(self):     
        headers = copy.copy(self.github_request_headers)
        headers['X-TS-User-Name'] = "some_user"
        validation_response = self.client.get(self.auth_validation_url, headers=headers)        
        self.assertEqual(validation_response.status_code, 401)
        self.assertIn("Not Authorized user", validation_response.content.decode())
    


    def test_login_validation_should_fail_with_wrong_ts_user_token(self):        
        headers = copy.copy(self.github_request_headers)        
        headers['X-TS-User-Token'] = "XYZ"
        validation_response = self.client.get(self.auth_validation_url, headers=headers)        
        self.assertEqual(validation_response.status_code, 401)
        self.assertIn("Not Authorized user", validation_response.content.decode())


    
    def test_login_validation_should_success_github(self):
        headers = copy.copy(self.github_request_headers)
        validation_response = self.client.get(self.auth_validation_url, headers=headers)        
        self.assertEqual(validation_response.status_code, 200)
        self.assertEqual(validation_response.json().get('_result').get('valid'), True)



    def test_login_validation_should_success_orcid(self):
        headers = copy.copy(self.orcid_request_headers)
        validation_response = self.client.get(self.auth_validation_url, headers=headers)            
        self.assertEqual(validation_response.status_code, 200)
        self.assertEqual(validation_response.json().get('_result').get('valid'), True)
