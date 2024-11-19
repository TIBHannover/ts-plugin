from django.db import models
from django.conf import settings
from typing import Optional, Union
from user_service.middlewares.request import get_client_id_from_request


class UserModel(models.Model):
    username = models.CharField()
    name = models.CharField(blank=True, null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    auth_provider = models.CharField()
    client_ts = models.CharField()
    user_extra = models.JSONField(blank=True, null=True)
    is_active = models.BooleanField(blank=True, null=True, default=True)
    is_blocked = models.BooleanField(blank=True, null=True, default=False)

    class Meta:
        db_table = "users"
        unique_together = (("username", "client_ts"),)

    def __str__(self) -> str:
        return f"<User {self.username}>"

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

    @staticmethod
    def get_by_username(username: str, client_ts: Optional[str] = None) -> dict:
        client = get_client_id_from_request() if not client_ts else client_ts
        user = UserModel.objects.filter(
            username == username, client_ts == client
        ).first()
        return user.to_dict()

    @staticmethod
    def get_by_id(user_id: Union[int, str], client_ts: Optional[str] = None) -> dict:
        client = get_client_id_from_request() if not client_ts else client_ts
        user = UserModel.objects.filter(id=user_id, client_ts=client).first()
        return user.to_dict() if user else None

    @staticmethod
    def get_user_id_by_username(
        username: str, client_ts: Optional[str] = None
    ) -> Optional[int]:
        client = get_client_id_from_request() if not client_ts else client_ts
        db_user = UserModel.objects.filter(username=username, client_ts=client).first()
        return db_user.id if db_user else None

    @staticmethod
    def get_user_name_by_id(
        user_id: Union[int, str], client_ts: Optional[str] = None
    ) -> Optional[str]:
        client = get_client_id_from_request() if not client_ts else client_ts
        db_user = UserModel.objects.filter(id=user_id, client_ts=client).first()
        return db_user.username if db_user else None

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
    def get_all_users() -> Optional[list]:
        users = UserModel.objects.all()
        return users


class UserTokenModel(models.Model):
    user = models.ForeignKey(UserModel, on_delete=models.CASCADE)
    created_at = models.DateTimeField()
    token = models.CharField()

    class Meta:
        db_table = "user_tokens"

    def __init__(
        self,
        user_id: Union[int, str, None] = None,
        created_at: Optional[str] = None,
        token: Optional[str] = None,
    ) -> None:
        self.user_id = user_id
        self.token = token
        self.created_at = created_at

    def __str__(self) -> str:
        return f"<UserToken {self.token}>"

    def get_user_token_record(self) -> Optional[object]:
        user_token_record = UserTokenModel.objects.filter(user == self.user_id).first()
        return user_token_record

    def get_user_token(self) -> Optional[str]:
        user_token_record = UserTokenModel.objects.filter(user == self.user_id).first()
        if user_token_record:
            return user_token_record.token
        return None

    def register_token(self) -> bool:
        user_token_record = UserTokenModel.objects.filter(id == self.id).first()
        if not user_token_record:
            self.save()
        return True

    def update_token(self, new_token: str) -> bool:
        user_token_record = UserTokenModel.objects.filter(id == self.id).first()
        if user_token_record:
            user_token_record.token = new_token
            user_token_record.save()
        return True
