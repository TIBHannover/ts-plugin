from user.models import UserModel, UserTokenModel, RoleModel
from note.models import NoteModel
from django.conf import settings
from datetime import datetime as _time

class TestHelper:

    client_ts = "general"

    @staticmethod
    def createGitHubUser():
        user_github = UserModel(
            username="github_" + settings.GITHUB_LOGIN_USERNAME,
            name=settings.GITHUB_LOGIN_USERNAME,
            created_at=_time.now(),
            auth_provider='github',
            client_ts=TestHelper.client_ts
        )
        user_github.save()
        user_token_github = UserTokenModel(
            user=user_github,
            created_at=_time.now(),
            token=settings.GITHUB_USER_TS_TOKEN
        )

        user_token_github.save()
        return user_github, user_token_github

    @staticmethod
    def createOrcidUser():
        user_orcid = UserModel(
            username="orcid_" + settings.ORCID_LOGIN_USERNAME,
            name=settings.ORCID_LOGIN_USERNAME,
            created_at=_time.now(),
            auth_provider='orcid',
            client_ts=TestHelper.client_ts
        )
        user_orcid.save()

        user_token_orcid = UserTokenModel(
            user=user_orcid,
            created_at=_time.now(),
            token=settings.ORCID_USER_TS_TOKEN
        )
        user_token_orcid.save()
        return user_orcid, user_token_orcid


    @staticmethod
    def createNote(user:UserModel):
        note = NoteModel(
            creator= user,
            created_at= _time.now(),
            ontology_id=  "vibso",
            content= "Test Content",
            title="Test Note",
            semantic_component_type= "class",
            client_ts= TestHelper.client_ts,
            semantic_component_iri= "some_iri",
            semantic_component_label= "Test Label",
            visibility= "public",
            parent_ontology_id="bfo",
        ) 
        note.save()
        return note


    @staticmethod
    def createSystemAdmin(user: UserModel):
        admin_role = RoleModel(
            user=user,
            created_at= _time.now(),
            target_object_id= "system",
            target_object_type= "system",
            role= "admin",
            client_ts= TestHelper.client_ts,
            role_holder_email= "me@tib.eu"
        )
        admin_role.save()
        return admin_role





        
