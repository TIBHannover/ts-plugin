from django.db import models
from django.conf import settings
from typing import Optional, Union
from user_service.middlewares.client_id import get_client_id_from_request
from datetime import datetime as _time
from django.contrib.auth.hashers import make_password


ALLOWED_ROLES = ["admin"]

# TODO: delete user mechanism


class UserModel(models.Model):
    # description,title,api_key,expires_at and owner are only for api key. we treat api key as a user and set the owner to the api key creator.
    username = models.CharField()
    name = models.CharField(blank=True, null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField(blank=True, null=True)
    auth_provider = models.CharField()
    client_ts = models.CharField()
    user_extra = models.JSONField(blank=True, null=True)
    is_active = models.BooleanField(blank=True, null=True, default=True)
    is_blocked = models.BooleanField(blank=True, null=True, default=False)
    description = models.CharField(blank=True, null=True)
    title = models.CharField(blank=True, null=True)
    api_key = models.CharField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    owner = models.ForeignKey(
        "self", on_delete=models.CASCADE, related_name="key_owner", null=True
    )

    class Meta:
        db_table = "ts_users"
        unique_together = (("username", "client_ts"),)

    def __str__(self) -> str:
        return f"<User {self.username} ({self.client_ts})>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "auth_provider": self.auth_provider,
            "client_ts": self.client_ts,
            "user_extra": self.user_extra,
            "is_active": self.is_active,
            "is_blocked": self.is_blocked,
            "description": self.description,
            "title": self.title,
            "expires_at": self.expires_at,
            "owner": self.owner.to_dict() if self.owner else None,
        }

    def register_user_if_not_exist(self):
        if self.auth_provider not in settings.AUTH_PROVIDERS:
            return "invalid_auth_provider"
        if self.client_ts not in settings.CLIENT_TERMINOLOGY_SERVICES:
            return "invalid_client_ts"
        user = UserModel.objects.filter(
            username=self.username, client_ts=self.client_ts
        ).first()

        if user and user.is_blocked:
            return "blocked"

        if not user:
            self.save()
            return self

        return user

    def get_user_admin_roles(self):
        roles = self.user_roles.all()
        result = {"system": [], "collection": [], "ontology": []}
        for r in roles:
            if r.role != "admin":
                continue
            try:
                result[r.target_object_type].append(r.target_object_id)
            except KeyError:
                continue
        return result

    @staticmethod
    def get_by_username(username: str, client_ts: Optional[str] = None):
        client = get_client_id_from_request() if not client_ts else client_ts
        user = UserModel.objects.filter(username=username, client_ts=client).first()
        return user

    @staticmethod
    def get_by_id(user_id: Union[int, str], client_ts: Optional[str] = None) -> dict:
        client = get_client_id_from_request() if not client_ts else client_ts
        user = UserModel.objects.filter(id=user_id, client_ts=client).first()
        return user.to_dict() if user else {}

    @staticmethod
    def get_user_id_by_username(
        username: str, client_ts: Optional[str] = None
    ) -> Optional[int]:
        client = get_client_id_from_request() if not client_ts else client_ts
        db_user = UserModel.objects.filter(username=username, client_ts=client).first()
        return db_user.id if db_user else False

    @staticmethod
    def get_user_name_by_id(
        user_id: Union[int, str], client_ts: Optional[str] = None
    ) -> Optional[str]:
        client = get_client_id_from_request() if not client_ts else client_ts
        db_user = UserModel.objects.filter(id=user_id, client_ts=client).first()
        return db_user.username if db_user else False

    @staticmethod
    def block_user(username: str) -> bool:
        db_user = UserModel.objects.filter(username=username).first()
        if db_user:
            db_user.is_blocked = True
            db_user.save()
            return True
        return False

    @staticmethod
    def save_user_extra(
        username: str, user_extra: dict, client_ts: Optional[str] = None
    ) -> bool:
        client = get_client_id_from_request() if not client_ts else client_ts
        db_user = UserModel.objects.filter(username=username, client_ts=client).first()
        if db_user:
            db_user.user_extra = user_extra
            db_user.save()
            return True
        return False

    @staticmethod
    def get_all_users() -> list:
        users = UserModel.objects.all()
        if users:
            return [user.to_dict() for user in users]
        return []


class RoleModel(models.Model):
    user = models.ForeignKey(
        UserModel, on_delete=models.CASCADE, related_name="user_roles"
    )
    created_at = models.DateTimeField()
    target_object_id = models.CharField()
    target_object_type = models.CharField()
    role = models.CharField()
    client_ts = models.CharField()
    role_holder_email = models.CharField(blank=True, null=True)

    class Meta:
        db_table = "roles"

    def to_dict(self):
        return {
            "created_at": self.created_at,
            "target_object_type": self.target_object_type,
            "role": self.role,
            "client_ts": self.client_ts,
        }

    def get_system_admin_emails(self) -> list:
        admins = RoleModel.objects.filter(
            client_ts=self.client_ts, target_object_type="system"
        )
        emails = []
        for admin in admins:
            emails.append(admin.role_holder_email)
        return emails

    def role_is_valid(self) -> bool:
        return self.role in ALLOWED_ROLES

    def __str__(self) -> str:
        return f"<Role {self.user_id}>"


class SearchSettingModel(models.Model):
    title = models.CharField()
    user = models.ForeignKey(
        UserModel, on_delete=models.CASCADE, related_name="search_settings"
    )
    description = models.CharField(blank=True, null=True)
    setting = models.JSONField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "search_settings"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "user_id": self.user.id,
            "setting": self.setting,
            "description": self.description,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def update(self, id: Union[int, str]) -> Union[dict, bool]:
        # check if the search setting title is unique for the user
        record = SearchSettingModel.objects.filter(
            user=self.user, title=self.title
        ).first()
        if record and record.id != id:
            return "Title already exists"

        record = SearchSettingModel.objects.filter(id=id, user=self.user).first()
        if record:
            record.title = self.title
            record.setting = self.setting
            record.description = self.description
            record.updated_at = _time.now()
            record.save()
            return record.to_dict()

        return False

    def can_visit_edit(self, user_id: Union[int, str]) -> bool:
        return self.user.id == user_id

    def __str__(self) -> str:
        return f"<SearchSettingModel {self.id}>"


class UserTokenModel(models.Model):
    # !!Attention: This model is not used anymore!!
    user = models.ForeignKey(
        UserModel, on_delete=models.CASCADE, related_name="user_api_keys"
    )
    created_at = models.DateTimeField()
    expires_at = models.DateTimeField(null=True)  # null means no expiration
    token = models.CharField()
    name = models.CharField(default="")
    description = models.CharField(blank=True, null=True)
    alt_username = models.CharField(
        blank=True, null=True
    )  # let user publich content with alternative username instead of his username

    class Meta:
        db_table = "api_keys"
        managed = False  # this model is not used anywhere, so we can disable it

    def save(self, **kwargs):
        self.token = make_password(self.token)
        self.created_at = _time.now()
        super().save(**kwargs)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user.id,
            "name": self.name,
            "description": self.description,
            "alt_username": self.alt_username,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }

    def __str__(self) -> str:
        return f"<APIKey {self.user.username} ({self.user.client_ts})>"
