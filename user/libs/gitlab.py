import requests
from django.conf import settings
from user.libs.auth_debug import debug_auth


class GitLabLib:
    @staticmethod
    def authenticate(code, client_ts_id=None, code_verifier=None):
        debug_auth("GitLab: selecting OAuth client configuration")
        redirect_url = settings.DEFAULT_FRONTEND_REDIRECT_URL
        if client_ts_id and client_ts_id == "general":
            redirect_url = settings.GENERAL_FRONTEND_REDIRECT_URL
        elif client_ts_id and client_ts_id == "nfdi4chem":
            redirect_url = settings.NFDI4CHEM_FRONTEND_REDIRECT_URL
        elif client_ts_id and client_ts_id == "nfdi4ing":
            redirect_url = settings.NFDI4ING_FRONTEND_REDIRECT_URL
        params = {
            "code": code,
            "client_id": settings.GITLAB_CLIENT_ID,
            "client_secret": settings.GITLAB_CLIENT_SECRET,
            "redirect_uri": redirect_url,
            "grant_type": "authorization_code",
        }
        if code_verifier:
            params["code_verifier"] = code_verifier
        debug_auth("GitLab: exchanging authorization code for access token")
        resp = requests.post(settings.GITLAB_TOKEN_URL, params=params)
        debug_auth(f"GitLab: token exchange returned HTTP {resp.status_code}")
        if resp.status_code == 200:
            debug_auth("GitLab: decoding token response")
            resp = resp.json()
            token = resp.get("access_token")
            debug_auth("GitLab: requesting user profile")
            user = requests.get(
                settings.GITLAB_USER_URL, headers={"Authorization": "Bearer " + token}
            )
            debug_auth(f"GitLab: user profile returned HTTP {user.status_code}")
            if user.status_code == 200:
                debug_auth("GitLab: decoding user profile")
                user_data = user.json()
                response_data = {}
                response_data["name"] = user_data.get("name")
                response_data["company"] = user_data.get("organization")
                response_data["gitlab_home"] = user_data.get("web_url")
                response_data["token"] = token
                response_data["ts_username"] = "gitlab_" + user_data.get("username")
                debug_auth("GitLab: provider authentication succeeded")
                return response_data

        debug_auth("GitLab: provider authentication rejected (token or profile response invalid)")
        return False

    @staticmethod
    def login_valid(user_auth_token):
        debug_auth("GitLab: validating existing provider login")
        if not user_auth_token:
            debug_auth("GitLab: login validation rejected; provider token missing")
            return False
        debug_auth("GitLab: requesting provider login validation")
        user = requests.get(
            settings.GITLAB_USER_URL,
            headers={"Authorization": "Bearer " + user_auth_token},
        )
        debug_auth(f"GitLab: login validation returned HTTP {user.status_code}")
        if user.status_code == 200 and user.json().get("username"):
            debug_auth("GitLab: provider login valid")
            return True
        debug_auth("GitLab: provider login rejected")
        return False
