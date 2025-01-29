# encoding: utf-8

from user.libs.github import GithubLib
from user.libs.gitlab import GitLabLib
from user.libs.orcid import OrcidLib
from user.libs.aai import AaiLib
from user_service.libs.utils import fetch_ontology_collections
from user.models import UserTokenModel, RoleModel, UserModel
import secrets
from datetime import datetime as _time
from typing import Optional, Union
from user_service.interfaces.i_editable_model_obj import IEditableModelObj
from django.core.exceptions import PermissionDenied, BadRequest
from django.conf import settings


class Auth:
    def __init__(
        self,
        code: Optional[str] = None,
        access_token: Optional[str] = None,
        auth_provider: Optional[str] = None,
        orcid_id: Optional[str] = None,
        client_ts_id: Optional[str] = None,
        client_ts_token: Optional[str] = None,
        user_id: Union[int, str, None] = None,
        user_token: Optional[str] = None,
        username: Optional[str] = None,
    ) -> None:
        self.code = code
        self.access_token = access_token
        self.auth_provider = auth_provider
        self.orcid_id = orcid_id
        self.client_ts_id = client_ts_id
        self.client_ts_token = client_ts_token
        self.user_id = user_id
        self.user_token = user_token


    def authenticate(self) -> Union[dict, bool]:
        if self.auth_provider == "github":
            return GithubLib.authenticate(code=self.code, client_ts_id=self.client_ts_id)
        elif self.auth_provider == "orcid":
            return OrcidLib.authenticate(code=self.code, client_ts_id=self.client_ts_id)
        elif self.auth_provider == "native":
            return AaiLib.authenticate(code=self.code, client_ts_id=self.client_ts_id)
        elif self.auth_provider == "gitlab":
            return GitLabLib.authenticate(code=self.code, client_ts_id=self.client_ts_id)
        return False


    def abort_if_not_authenticated(self) -> None:
        login_validity = False
        self.abort_if_client_app_not_valid()
        self.abort_if_not_auth_provider()
        self.abort_if_user_does_not_exist()
        self.abort_if_user_token_is_not_valid()
        self.abort_if_user_is_blocked()
        if self.auth_provider == "github":
            login_validity = GithubLib.login_valid(user_auth_token=self.access_token)
        elif self.auth_provider == "orcid":
            login_validity = OrcidLib.login_valid(user_auth_token=self.access_token, orcid_id=self.orcid_id)
        elif self.auth_provider == "native":
            login_validity = AaiLib.is_login_valid(user_auth_token=self.access_token)
        elif self.auth_provider == "gitlab":
            login_validity = GitLabLib.login_valid(user_auth_token=self.access_token)

        if not login_validity:
            raise PermissionDenied("Not Authorized")


    def user_is_guest(self) -> Optional[bool]:
        try:
            login_validity = False
            self.abort_if_not_auth_provider()
            self.abort_if_user_does_not_exist()
            self.abort_if_user_token_is_not_valid()
            if self.auth_provider == "github":
                login_validity = GithubLib.login_valid(user_auth_token=self.access_token)
            elif self.auth_provider == "orcid":
                login_validity = OrcidLib.login_valid(user_auth_token=self.access_token, orcid_id=self.orcid_id)
            elif self.auth_provider == "native":
                login_validity = AaiLib.is_login_valid(user_auth_token=self.access_token)
            elif self.auth_provider == "gitlab":
                login_validity = GitLabLib.login_valid(user_auth_token=self.access_token)

            if not login_validity:
                raise PermissionDenied("Not Authorized")

            return False
        except:
            # raise
            return True


    def abort_if_client_app_not_valid(self) -> Optional[bool]:
        if not self.client_ts_id or self.client_ts_id not in getattr(settings, "CLIENT_TERMINOLOGY_SERVICES", []):
            raise PermissionDenied("Client application is not allowed to use this service.")

        if not self.client_ts_token or self.client_ts_token != settings.FRONTEDN_AUTH_TOKEN:
            raise PermissionDenied("Client application is not allowed to use this service.")

        return True


    def abort_if_not_auth_provider(self) -> Optional[bool]:
        if not self.auth_provider or self.auth_provider not in getattr(settings, "AUTH_PROVIDERS", []):
            raise PermissionDenied("auth provider is not clear")
        return True


    def abort_if_user_does_not_exist(self) -> Optional[bool]:
        if not self.user_id:
            raise PermissionDenied("Not Authorized user")
        return True


    def abort_if_user_is_blocked(self) -> None:
        if not self.user_id:
            raise BadRequest("incomplete request")
        user = UserModel.get_by_id(self.user_id)
        if user["is_blocked"]:
            raise PermissionDenied("Not Authorized user")


    def get_or_register_user_token_if_not_exist(self) -> str:
        user_token = UserTokenModel.objects.filter(user__id=self.user_id).first()
        if self.user_id and user_token:
            return user_token.token

        token = secrets.token_urlsafe(32)
        user = UserModel.objects.get(id=self.user_id)
        new_token = UserTokenModel()
        new_token.user = user
        new_token.created_at = _time.now()
        new_token.token = token 
        new_token.save()
        return token


    def abort_if_user_token_is_not_valid(self) -> Optional[bool]:
        if not self.user_token:
            raise PermissionDenied("Not Authorized user token")

        user_token = UserTokenModel.objects.filter(user__id=self.user_id).first()
        if not user_token or user_token.token != self.user_token:
            raise PermissionDenied("Not Authorized user token")

        return True

    def is_user_admin_for_entity(self, ontologyId: str, collectionId: Optional[str] = None) -> bool:
        system_admin = RoleModel.objects.filter(
            user__id=self.user_id,
            target_object_id="system",
            target_object_type="system",
            client_ts=self.client_ts_id,
        ).first()
        if system_admin:
            # system admins are admin for all entities.
            return True

        if collectionId:
            # if the request is to check the collection admin status for a user.
            collectio_admin = RoleModel.objects.filter(
                user__id=self.user_id,
                target_object_id=collectionId,
                target_object_type="collection",
                client_ts=self.client_ts_id,
            ).first()
            if collectio_admin:
                return True

        if ontologyId:
            ontology_admin = RoleModel.objects.filter(
                user__id=self.user_id,
                target_object_id=ontologyId,
                target_object_type="ontology",
                client_ts=self.client_ts_id,
            )
            if ontology_admin:
                return True

            # if the user is not ontology admin directly, check if the user is the collection admin that contains that ontology.
            collections = fetch_ontology_collections(ontologyId)
            for col in collections:
                collectio_admin = RoleModel.objects.filter(
                    user__id=self.user_id,
                    target_object_id=col,
                    target_object_type="collection",
                    client_ts=self.client_ts_id,
                ).first()
                if collectio_admin:
                    return True

        return False


    def user_can_edit_object(
        self,
        objectModel: IEditableModelObj,
        object_id: Union[int, str],
        role_target_object_id: str = ""
    ) -> bool:
        if not self.user_id:
            return False
        if objectModel.user_can_edit(object_id, self.user_id):
            return True

        visibility = objectModel.get_visibility(object_id)
        if self.is_user_admin_for_entity(ontologyId=role_target_object_id) and visibility != "me":
            return True

        return False
