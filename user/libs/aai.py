import requests
from django.conf import settings


class AaiLib:
    @staticmethod
    def authenticate(code):
        data = {
            "code": code,
            "client_id": settings.AAI_CLIENT_ID,
            "client_secret": settings.AAI_CLIENT_SECRET,
            "redirect_uri": settings.FRONTEND_REDIRECT_URL,
            "grant_type": "authorization_code",
        }
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        resp = requests.post(settings.AAI_TOKEN_URL, data=data, headers=headers)
        if resp.status_code == 200:
            resp = resp.json()
            token = resp.get("access_token")
            if not token:
                return False
            user = requests.get(
                settings.AAI_USER_URL, headers={"Authorization": "Bearer " + token}
            )
            if user.status_code == 200:
                user = user.json()
                user_info = {}
                user_info["token"] = token
                user_info["name"] = user.get("name")
                user_info["ts_username"] = "native_" + user.get("given_name")
                return user_info

        return False

    @staticmethod
    def is_login_valid(user_auth_token):
        if not user_auth_token or user_auth_token == "":
            return False

        response = requests.get(
            settings.AAI_USER_URL,
            headers={"Authorization": "Bearer " + user_auth_token},
        )
        if response.status_code == 200:
            return True
        return False
