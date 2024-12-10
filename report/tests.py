from django.test import TestCase
from user.models import RoleModel, UserModel
from note.models import NoteModel
from datetime import datetime as _time
from django.conf import settings
from user_service.libs.test_config import BaseTest
import copy


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


        user = UserModel.objects.filter(
            username=cls.test_github_username,
            name=settings.GITHUB_LOGIN_USERNAME,
            created_at=_time.now(),
            auth_provider='github',
            client_ts='generel'
        )
        user.save()
        admin_role = RoleModel(
            user=user,
            created_at= _time.now(),
            target_object_id= "system",
            target_object_type= "system",
            role= "admin",
            client_ts= "general",
            role_holder_email= "me@tib.eu"
        )
        admin_role.save()

        note = NoteModel(
            creator= user,
            created_at= _time.now(),
            ontology_id= cls.test_ontology_id,
            content= "Test Content",
            title="Test Note",
            semantic_component_type= "class",
            client_ts= "general",
            semantic_component_iri= "some_iri",
            semantic_component_label= "Test Label",
            visibility= "public",
            parent_ontology_id=cls.parent_ontology_id,
        ) 
        note.save()
        cls.public_note_id = note.id


        cls.report_form_data['objectId'] = note.id   
        cls.resolve_report_form_data['objectId'] = note.id 
        cls.report_create_url = '/report/create' 
        cls.report_resolve_url = '/report/resolve'        


    
    def test_report_create_fail_for_guest_user(self):        
        headers = copy.copy(self.guest_request_headers)        
        response = self.client.post(self.report_create_url, headers=headers, data=self.report_form_data)                
        self.assertEqual(response.status_code, 401)
        self.assertIn("Not Authorized user", response.content.decode())
    


    def test_report_create_success_user(self):        
        headers = copy.copy(self.orcid_request_headers)        
        response = self.client.post(self.report_create_url, headers=headers, data=self.report_form_data)                        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['_result']['report_created'], True)

    


    def test_report_resolve_fail_guest_user(self):        
        headers = copy.copy(self.guest_request_headers)        
        response = self.client.post(self.report_resolve_url, headers=headers, data=self.resolve_report_form_data)                        
        self.assertEqual(response.status_code, 401)
    


    def test_report_resolve_fail_non_admin_user(self):        
        headers = copy.copy(self.orcid_request_headers)        
        response = self.client.post(self.report_resolve_url, headers=headers, data=self.resolve_report_form_data)                        
        self.assertEqual(response.status_code, 401)
    


    def test_report_resolve_success_admin_user(self):        
        headers = copy.copy(self.github_request_headers)        
        response = self.client.post(self.report_resolve_url, headers=headers, data=self.resolve_report_form_data)                        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['_result']['resolved'], True)
