import requests
from django.conf import settings
from user.libs.auth_debug import debug_auth


class AaiLib:
    @staticmethod
    def authenticate(code, client_ts_id=None, code_verifier=None):
        debug_auth("AAI: selecting OAuth client configuration")
        redirect_url = settings.DEFAULT_FRONTEND_REDIRECT_URL
        if client_ts_id and client_ts_id == "general":
            redirect_url = settings.GENERAL_FRONTEND_REDIRECT_URL
        elif client_ts_id and client_ts_id == "nfdi4chem":
            redirect_url = settings.NFDI4CHEM_FRONTEND_REDIRECT_URL

        data = {
            "code": code,
            "client_id": settings.AAI_CLIENT_ID,
            "client_secret": settings.AAI_CLIENT_SECRET,
            "redirect_uri": redirect_url,
            "grant_type": "authorization_code",
        }
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        debug_auth("AAI: exchanging authorization code for access token")
        resp = requests.post(settings.AAI_TOKEN_URL, data=data, headers=headers)
        debug_auth(f"AAI: token exchange returned HTTP {resp.status_code}")
        if resp.status_code == 200:
            debug_auth("AAI: decoding token response")
            resp = resp.json()
            token = resp.get("access_token")
            if not token:
                debug_auth("AAI: token response has no access token; authentication rejected")
                return False
            debug_auth("AAI: requesting user profile")
            user = requests.get(
                settings.AAI_USER_URL, headers={"Authorization": "Bearer " + token}
            )
            debug_auth(f"AAI: user profile returned HTTP {user.status_code}")
            if user.status_code == 200:
                debug_auth("AAI: decoding user profile")
                user = user.json()
                user_info = {}
                user_info["token"] = token
                user_info["name"] = user.get("name")
                user_info["ts_username"] = "native_" + user.get("given_name")
                debug_auth("AAI: provider authentication succeeded")
                return user_info

        debug_auth("AAI: provider authentication rejected (token or profile response invalid)")
        return False

    @staticmethod
    def is_login_valid(user_auth_token):
        debug_auth("AAI: validating existing provider login")
        if not user_auth_token or user_auth_token == "":
            debug_auth("AAI: login validation rejected; provider token missing")
            return False

        debug_auth("AAI: requesting provider login validation")
        response = requests.get(
            settings.AAI_USER_URL,
            headers={"Authorization": "Bearer " + user_auth_token},
        )
        debug_auth(f"AAI: login validation returned HTTP {response.status_code}")
        if response.status_code == 200:
            debug_auth("AAI: provider login valid")
            return True
        debug_auth("AAI: provider login rejected")
        return False
