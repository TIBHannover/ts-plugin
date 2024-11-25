import requests
from django.conf import settings


class GitLabLib:
    @staticmethod
    def authenticate(code, client_ts_id=None):
        redirect_url = settings.DEFAULT_FRONTEND_REDIRECT_URL
        if client_ts_id and client_ts_id == "general":
            redirect_url = settings.GENERAL_FRONTEND_REDIRECT_URL
        elif client_ts_id and client_ts_id == "nfdi4chem":
            redirect_url = settings.NFDI4CHEM_FRONTEND_REDIRECT_URL
        params = {
            "code": code,
            "client_id": settings.GITLAB_CLIENT_ID,
            "client_secret": settings.GITLAB_CLIENT_SECRET,
            "redirect_uri": redirect_url,
            "grant_type": "authorization_code",
        }
        resp = requests.post(settings.GITLAB_TOKEN_URL, params=params)
        if resp.status_code == 200:
            resp = resp.json()
            token = resp.get("access_token")
            user = requests.get(
                settings.GITLAB_USER_URL, headers={"Authorization": "Bearer " + token}
            )
            if user.status_code == 200:
                user_data = user.json()
                response_data = {}
                response_data["name"] = user_data.get("name")
                response_data["company"] = user_data.get("organization")
                response_data["gitlab_home"] = user_data.get("web_url")
                response_data["token"] = token
                response_data["ts_username"] = "gitlab_" + user_data.get("username")
                return response_data

        return False

    @staticmethod
    def login_valid(user_auth_token):
        if not user_auth_token:
            return False
        user = requests.get(
            settings.GITLAB_USER_URL,
            headers={"Authorization": "Bearer " + user_auth_token},
        )
        if user.status_code == 200 and user.json().get("username"):
            return True
        return False
