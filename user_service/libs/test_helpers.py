from user.models import UserModel, RoleModel, SearchSettingModel, UserTokenModel
from note.models import NoteModel, NoteCommentModel
from collection.models import CollectionModel
from term_set.models import TermSetModel, TermsModel
from django.conf import settings
from datetime import datetime as _time
import datetime
import uuid
from jose import jwt, JWTError
import secrets
from django.contrib.auth.hashers import make_password


class TestHelper:
    client_ts = "general"

    @staticmethod
    def generate_jwt(payload, username, token, orcid_id=""):
        payload["exp"] = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
            60 * 5
        )
        payload["ts_username"] = username
        payload["orcid_id"] = orcid_id
        payload["token"] = token
        jwt_token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
        return jwt_token

    @staticmethod
    def generate_csrf_token() -> str:
        return jwt.encode(
            {"csrf": secrets.token_urlsafe(32)},
            settings.SECRET_KEY,
            algorithm="HS256",
        )

    @staticmethod
    def generate_jwt_cookie() -> str:
        return jwt.encode(
            {"jwt": secrets.token_urlsafe(32)},
            settings.SECRET_KEY,
            algorithm="HS256",
        )

    @staticmethod
    def validate_and_return_jwt_payload(token: str):
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            return payload
        except JWTError:
            return {}

    @staticmethod
    def createGitHubUser() -> UserModel:
        user_github = UserModel(
            username="github_" + settings.GITHUB_LOGIN_USERNAME,
            name=settings.GITHUB_LOGIN_USERNAME,
            created_at=_time.now(),
            auth_provider="github",
            client_ts=TestHelper.client_ts,
        )
        user_github.save()
        return user_github

    @staticmethod
    def createOrcidUser() -> UserModel:
        user_orcid = UserModel(
            username="orcid_" + settings.ORCID_LOGIN_USERNAME,
            name=settings.ORCID_LOGIN_USERNAME,
            created_at=_time.now(),
            auth_provider="orcid",
            client_ts=TestHelper.client_ts,
        )
        user_orcid.save()
        return user_orcid

    @staticmethod
    def createApiKeyUser(
        user: UserModel, name: str, description: str, title: str
    ) -> UserModel:
        api_key = UserModel(
            username="api_" + user.username,
            name=name,
            auth_provider="apikey",
            client_ts=user.client_ts,
            created_at=_time.now(),
            description=description,
            title=title,
            api_key=make_password(secrets.token_urlsafe(32)),
            expires_at=None,
            owner=user,
            user_extra={},
        )
        api_key.save()
        return api_key

    @staticmethod
    def createNote(
        user: UserModel,
        visibility="public",
        component_type="ontology",
        ontology_id="vibso",
        parent_ontology_id="",
    ) -> NoteModel:
        note = NoteModel(
            creator=user,
            created_at=_time.now(),
            ontology_id=ontology_id,
            content="Test Content",
            title="Test Note",
            semantic_component_type=component_type,
            semantic_component_iri="some_iri",
            semantic_component_label="Test Label",
            visibility=visibility,
            parent_ontology_id=parent_ontology_id,
        )
        note.save()
        return note

    @staticmethod
    def createCommentForNote(user: UserModel, note: NoteModel) -> NoteCommentModel:
        comment = NoteCommentModel(
            creator=user, created_at=_time.now(), content="test comment", note=note
        )
        comment.save()
        return comment

    @staticmethod
    def createSystemAdmin(user: UserModel) -> RoleModel:
        admin_role = RoleModel(
            user=user,
            created_at=_time.now(),
            target_object_id="system",
            target_object_type="system",
            role="admin",
            client_ts=TestHelper.client_ts,
            role_holder_email="me@tib.eu",
        )
        admin_role.save()
        return admin_role

    @staticmethod
    def createRole(
        user: UserModel, target_id: str, target_type: str, role="admin"
    ) -> RoleModel:
        role = RoleModel(
            user=user,
            created_at=_time.now(),
            target_object_id=target_id,
            target_object_type=target_type,
            role=role,
            client_ts=TestHelper.client_ts,
            role_holder_email="me@tib.eu",
        )
        role.save()
        return role

    @staticmethod
    def create_collection(
        user: UserModel, title: str, content: str, ontology_ids: [str]
    ) -> CollectionModel:
        collection_model = CollectionModel(
            title=title,
            owner=user,
            created_at=_time.now(),
            description=content,
            ontology_ids=ontology_ids,
        )
        collection_model.save()
        return collection_model

    @staticmethod
    def create_search_setting(
        user: UserModel, title: str, description: str, settings: dict
    ) -> SearchSettingModel:
        setting_model = SearchSettingModel(
            title=title,
            user=user,
            created_at=_time.now(),
            description=description,
            setting=settings,
        )
        setting_model.save()
        return setting_model

    @staticmethod
    def create_term_set(
        user: UserModel, name: str, visibility: str, description: str, terms: list
    ) -> TermSetModel:
        term_set = TermSetModel()
        term_set.id = str(uuid.uuid4())
        term_set.name = name
        term_set.created_at = _time.now()
        term_set.creator = user
        term_set.description = description
        term_set.visibility = visibility
        term_set.save()
        terms_to_save = []
        term_set.terms.all().delete()
        for term in terms:
            term_model = TermsModel()
            term_model.iri = term["iri"]
            term_model.term_type = (
                term["type"][0] if isinstance(term["type"], list) else term["type"]
            )
            term_model.metadata = term
            term_model.term_set = term_set
            terms_to_save.append(term_model)

        TermsModel.objects.bulk_create(terms_to_save)
        return term_set.to_dict()
