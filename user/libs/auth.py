# encoding: utf-8

from user.libs.github import GithubLib
from user.libs.gitlab import GitLabLib
from user.libs.orcid import OrcidLib
from user.libs.aai import AaiLib
from user.models import UserModel
from typing import Optional, Union
from django.core.exceptions import PermissionDenied, BadRequest
from django.conf import settings
from user_service.interfaces.i_editable_model_obj import IEditableModelObj
from user_service.middlewares.request import get_headers_dict
from jose import jwt
from user_service.middlewares.request import get_jwt_token_from_request
from user_service.middlewares.request import get_username_from_request


class Auth:
    def __init__(
        self,
        code: Optional[str] = None,
        auth_provider: Optional[str] = None,
        orcid_id: Optional[str] = None,
        client_ts_id: Optional[str] = None,
        client_ts_token: Optional[str] = None,
        user_id: Union[int, str, None] = None,
    ) -> None:
        auth_object_dict = get_headers_dict()
        self.code = code or auth_object_dict["code"]
        self.access_token = Auth.get_provider_token_from_jwt_payload()
        self.auth_provider = auth_provider or auth_object_dict["auth_provider"]
        self.orcid_id = orcid_id or auth_object_dict["orcid_id"]
        self.client_ts_id = client_ts_id or auth_object_dict["client_ts_id"]
        if not user_id:
            userId = UserModel.get_user_id_by_username(
                username=get_username_from_request()
            )
            self.user_id = userId
        else:
            self.user_id = user_id

    def authenticate(self) -> Union[dict, bool]:
        match self.auth_provider:
            case "github":
                return GithubLib.authenticate(
                    code=self.code, client_ts_id=self.client_ts_id
                )
            case "orcid":
                return OrcidLib.authenticate(
                    code=self.code, client_ts_id=self.client_ts_id
                )
            case "native":
                return AaiLib.authenticate(
                    code=self.code, client_ts_id=self.client_ts_id
                )
            case "gitlab":
                return GitLabLib.authenticate(
                    code=self.code, client_ts_id=self.client_ts_id
                )
            case _:
                return False

    def login_is_valid(self) -> bool:
        match self.auth_provider:
            case "github":
                return GithubLib.login_valid(user_auth_token=self.access_token)
            case "orcid":
                return OrcidLib.login_valid(
                    user_auth_token=self.access_token, orcid_id=self.orcid_id
                )
            case "native":
                return AaiLib.is_login_valid(user_auth_token=self.access_token)
            case "gitlab":
                return GitLabLib.login_valid(user_auth_token=self.access_token)
            case _:
                return False

    def abort_if_not_authenticated(self) -> None:
        login_validity = False
        self.abort_if_user_token_is_not_valid()
        self.abort_if_not_auth_provider()
        self.abort_if_userId_is_missing()
        self.abort_if_user_is_blocked()
        login_validity = self.login_is_valid()
        if not login_validity:
            raise PermissionDenied("Not Authorized")

    def user_is_guest(self) -> Optional[bool]:
        try:
            login_validity = False
            self.abort_if_not_auth_provider()
            self.abort_if_userId_is_missing()
            self.abort_if_user_token_is_not_valid()
            login_validity = self.login_is_valid()
            if not login_validity:
                raise PermissionDenied("Not Authorized")
            return False
        except:
            return True

    def abort_if_client_app_not_valid(self) -> Optional[bool]:
        if not self.client_ts_id or self.client_ts_id not in getattr(
            settings, "CLIENT_TERMINOLOGY_SERVICES", []
        ):
            raise PermissionDenied(
                "Client application is not allowed to use this service."
            )

        if (
            not self.client_ts_token
            or self.client_ts_token != settings.FRONTEDN_AUTH_TOKEN
        ):
            raise PermissionDenied(
                "Client application is not allowed to use this service."
            )

        return True

    def abort_if_not_auth_provider(self) -> Optional[bool]:
        if not self.auth_provider or self.auth_provider not in getattr(
            settings, "AUTH_PROVIDERS", []
        ):
            raise PermissionDenied("auth provider is not clear")
        return True

    def abort_if_userId_is_missing(self) -> Optional[bool]:
        if not self.user_id:
            raise PermissionDenied("Not Authorized user")
        return True

    def abort_if_user_is_blocked(self) -> None:
        if not self.user_id:
            raise BadRequest("incomplete request")
        user = UserModel.get_by_id(self.user_id)
        if user["is_blocked"]:
            raise PermissionDenied("Not Authorized user")

    def abort_if_user_token_is_not_valid(self) -> Optional[bool]:
        token = get_jwt_token_from_request()
        try:
            jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        except:
            raise PermissionDenied("Not Authorized user token")
        return True

    def is_user_admin_for_entity(
        self, ontologyId: str, collectionId: Optional[str] = None
    ) -> bool:
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
        role_target_object_id: str = "",
    ) -> bool:
        if not self.user_id:
            return False
        if objectModel.user_can_edit(object_id, self.user_id):
            return True

        visibility = objectModel.get_visibility(object_id)
        if (
            self.is_user_admin_for_entity(ontologyId=role_target_object_id)
            and visibility != "me"
        ):
            return True

        return False

    @staticmethod
    def get_jwt_token_payload():
        token = get_jwt_token_from_request()
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            return payload
        except:
            return {}

    @staticmethod
    def get_provider_token_from_jwt_payload():
        # returns the oAuth provider token. used to call the provider API (example GitHub)
        token = get_jwt_token_from_request()
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            return payload["token"]
        except:
            return ""
