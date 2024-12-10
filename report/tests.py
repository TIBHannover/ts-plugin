from django.test import TestCase
from user.models import RoleModel, UserModel, UserTokenModel
from note.models import NoteModel
from datetime import datetime as _time
from django.conf import settings
from user_service.libs.test_config import BaseTest
import copy
import json


class TestReport(TestCase, BaseTest):

    @classmethod
    def setUpTestData(cls) -> None:
        
        cls.report_form_data = {
            "objectType": "note",
            "objectId": 1,
            "content": "Test content for report",
            "ontology": "vibso"
        }

        cls.resolve_report_form_data = {
            "objectType": "note",
            "objectId": 1,
            "action": "none",
            "creatorUsername": "test-user"
        }


        user_github = UserModel(
            username=cls.test_github_username,
            name=settings.GITHUB_LOGIN_USERNAME,
            created_at=_time.now(),
            auth_provider='github',
            client_ts=cls.client_ts_id
        )
        user_orcid = UserModel(
            username=cls.test_orcid_username,
            name=settings.ORCID_LOGIN_USERNAME,
            created_at=_time.now(),
            auth_provider='orcid',
            client_ts=cls.client_ts_id
        )
        user_github.save()
        user_orcid.save()
        user_token_github = UserTokenModel(
            user=user_github,
            created_at=_time.now(),
            token=cls.test_github_user_ts_token
        )
        user_token_orcid = UserTokenModel(
            user=user_orcid,
            created_at=_time.now(),
            token=cls.test_orcid_user_ts_token
        )

        user_token_github.save()
        user_token_orcid.save()
        admin_role = RoleModel(
            user=user_github,
            created_at= _time.now(),
            target_object_id= "system",
            target_object_type= "system",
            role= "admin",
            client_ts= cls.client_ts_id,
            role_holder_email= "me@tib.eu"
        )
        admin_role.save()

        note = NoteModel(
            creator= user_github,
            created_at= _time.now(),
            ontology_id= cls.test_ontology_id,
            content= "Test Content",
            title="Test Note",
            semantic_component_type= "class",
            client_ts= cls.client_ts_id,
            semantic_component_iri= "some_iri",
            semantic_component_label= "Test Label",
            visibility= "public",
            parent_ontology_id=cls.test_parent_ontology_id,
        ) 
        note.save()
        cls.public_note_id = note.id


        cls.report_form_data['objectId'] = note.id   
        cls.resolve_report_form_data['objectId'] = note.id 
        cls.report_create_url = '/report/create/' 
        cls.report_resolve_url = '/report/resolve/'        


    
    def test_report_create_fail_for_guest_user(self):        
        headers = copy.copy(self.guest_request_headers)        
        response = self.client.post(self.report_create_url, headers=headers, data=json.dumps(self.report_form_data), content_type="application/json")                
        self.assertEqual(response.status_code, 401)
        self.assertIn("Not Authorized user", response.content.decode())



    def test_report_create_success_user(self):        
        headers = copy.copy(self.orcid_request_headers)        
        response = self.client.post(self.report_create_url, headers=headers, data=json.dumps(self.report_form_data), content_type="application/json")                        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['_result']['report_created'], True)

    


    def test_report_resolve_fail_guest_user(self):        
        headers = copy.copy(self.guest_request_headers)        
        response = self.client.post(self.report_resolve_url, headers=headers, data=json.dumps(self.resolve_report_form_data), content_type="application/json")                        
        self.assertEqual(response.status_code, 401)



    def test_report_resolve_fail_non_admin_user(self):        
        headers = copy.copy(self.orcid_request_headers)        
        response = self.client.post(self.report_resolve_url, headers=headers, data=json.dumps(self.resolve_report_form_data), content_type="application/json")                        
        self.assertEqual(response.status_code, 401)



    def test_report_resolve_success_admin_user(self):        
        headers = copy.copy(self.github_request_headers)        
        response = self.client.post(self.report_resolve_url, headers=headers, data=json.dumps(self.resolve_report_form_data), content_type="application/json")                    
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['_result']['resolved'], True)
