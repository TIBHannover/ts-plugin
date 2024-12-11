from django.test import TestCase
from user_service.libs.test_config import BaseTest
from user.models import RoleModel
from user_service.libs.test_helpers import TestHelper
from datetime import datetime as _time


class TestRole(TestCase, BaseTest):

    @classmethod
    def setUpTestData(self) -> None:
        self.user,_ = TestHelper.createGitHubUser()

        
    def test_add_role_success(self):
        role_model_record_dict = {
            "user": self.user,
            "created_at": _time.now(),
            "target_object_id": "vibso",                
            "target_object_type": "ontology",
            "role": "admin",
            "client_ts": "general",
            "role_holder_email": "me@tib.eu"
        }            
        role_model_object = RoleModel(**role_model_record_dict)
        role_model_object.save()
        self.assertNotEqual(role_model_object.id, None)



    def test_get_role_success(self):
        role_model_record_dict = {
            "user": self.user,
            "created_at": _time.now(),
            "target_object_id": "vibso",                
            "target_object_type": "ontology",
            "role": "admin",
            "client_ts": "general",
            "role_holder_email": "me@tib.eu"
        }            
        role_model_object = RoleModel(**role_model_record_dict)
        role_model_object.save()
        roles = self.user.user_roles.all()
        self.assertEqual(len(roles), 1)
        self.assertEqual(roles[0].target_object_type, "ontology")
        self.assertEqual(roles[0].target_object_id, "vibso")


