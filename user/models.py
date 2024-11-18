from django.db import models


class Users(models.Model):
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


class UserTokens(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE)
    created_at = models.DateTimeField()
    token = models.CharField()

    class Meta:
        db_table = "user_tokens"
