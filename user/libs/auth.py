# encoding: utf-8

from user_service.libs.github import GithubLib
from user_service.libs.gitlab import GitLabLib
from user_service.libs.orcid import OrcidLib
from user_service.libs.aai import AaiLib
from user_service.libs.utils import Utils
from flask import abort, current_app
from user_service.models.user_token import UserTokenModel
from user_service.models.user import UserModel
from user_service.models.role import RoleModel
import secrets
from datetime import datetime as _time
from typing import Optional, Union
from user_service.interfaces.i_editable_model_obj import IEditableModelObj


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
            return GithubLib.authenticate(
                code=self.code, app=current_app, client_ts_id=self.client_ts_id
            )
        elif self.auth_provider == "orcid":
            return OrcidLib.authenticate(code=self.code, app=current_app)
        elif self.auth_provider == "native":
            return AaiLib.authenticate(code=self.code, app=current_app)
        elif self.auth_provider == "gitlab":
            return GitLabLib.authenticate(
                code=self.code, app=current_app, client_ts_id=self.client_ts_id
            )
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
            login_validity = OrcidLib.login_valid(
                user_auth_token=self.access_token, orcid_id=self.orcid_id
            )
        elif self.auth_provider == "native":
            login_validity = AaiLib.is_login_valid(user_auth_token=self.access_token)
        elif self.auth_provider == "gitlab":
            login_validity = GitLabLib.login_valid(user_auth_token=self.access_token)

        if not login_validity:
            abort(401, "Not Authorized")

    def user_is_guest(self) -> Optional[bool]:
        try:
            login_validity = False
            self.abort_if_not_auth_provider()
            self.abort_if_user_does_not_exist()
            self.abort_if_user_token_is_not_valid()
            if self.auth_provider == "github":
                login_validity = GithubLib.login_valid(
                    user_auth_token=self.access_token
                )
            elif self.auth_provider == "orcid":
                login_validity = OrcidLib.login_valid(
                    user_auth_token=self.access_token, orcid_id=self.orcid_id
                )
            elif self.auth_provider == "native":
                login_validity = AaiLib.is_login_valid(
                    user_auth_token=self.access_token
                )
            elif self.auth_provider == "gitlab":
                login_validity = GitLabLib.login_valid(
                    user_auth_token=self.access_token
                )

            if not login_validity:
                abort(401, "Not Authorized")

            return False
        except:
            # raise
            return True

    def abort_if_client_app_not_valid(self) -> Optional[bool]:
        if not self.client_ts_id or self.client_ts_id not in current_app.config.get(
            "CLIENT_TERMINOLOGY_SERVICES", []
        ):
            abort(401, "Client application is not allowed to use this service.")

        if not self.client_ts_token or self.client_ts_token != current_app.config.get(
            "FRONTEDN_AUTH_TOKEN"
        ):
            abort(401, "Client application is not allowed to use this service.")

        return True

    def abort_if_not_auth_provider(self) -> Optional[bool]:
        if not self.auth_provider or self.auth_provider not in current_app.config.get(
            "AUTH_PROVIDERS", []
        ):
            abort(403, "auth provider is not clear")
        return True

    def abort_if_user_does_not_exist(self) -> Optional[bool]:
        if not self.user_id:
            abort(401, "Not Authorized user")
        return True

    def abort_if_user_is_blocked(self) -> None:
        if not self.user_id:
            abort(403, "incomplete request")
        user = UserModel.get_by_id(self.user_id)
        if user["is_blocked"]:
            abort(401, "Not Authorized user")

    def get_or_register_user_token_if_not_exist(self) -> str:
        user_token_object = UserTokenModel(user_id=self.user_id)
        user_token = user_token_object.get_user_token()
        if self.user_id and user_token:
            return user_token

        new_token = secrets.token_urlsafe(32)
        created_at = _time.now()
        user_token_object.created_at = created_at
        user_token_object.token = new_token
        user_token_object.register_token()
        return new_token

    def abort_if_user_token_is_not_valid(self) -> Optional[bool]:
        if not self.user_token:
            abort(401, "Not Authorized user token")

        user_token_model = UserTokenModel(user_id=self.user_id)
        user_token_in_db = user_token_model.get_user_token()
        if not user_token_in_db or user_token_in_db != self.user_token:
            abort(401, "Not Authorized user token")

        return True

    def is_user_admin_for_entity(
        self, ontologyId: str, collectionId: Optional[str] = None
    ) -> bool:
        role = RoleModel(
            user_id=self.user_id,
            target_object_id="system",
            target_object_type="system",
            client=self.client_ts_id,
        )
        if role.get_by_user_and_target():
            return True

        if collectionId:
            role = RoleModel(
                user_id=self.user_id,
                target_object_id=collectionId,
                target_object_type="collection",
                client=self.client_ts_id,
            )
            if role.get_by_user_and_target():
                return True

        if ontologyId:
            role = RoleModel(
                user_id=self.user_id,
                target_object_id=ontologyId,
                target_object_type="ontology",
                client=self.client_ts_id,
            )
            if role.get_by_user_and_target():
                return True

            collections = Utils.fetch_ontology_collections(ontologyId)
            for col in collections:
                role = RoleModel(
                    user_id=self.user_id,
                    target_object_id=col,
                    target_object_type="collection",
                    client=self.client_ts_id,
                )
                if role.get_by_user_and_target():
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
