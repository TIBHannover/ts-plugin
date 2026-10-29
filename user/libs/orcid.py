import requests
from django.conf import settings
from user.libs.auth_debug import debug_auth


class OrcidLib:
    @staticmethod
    def authenticate(code, client_ts_id=None, code_verifier=None):
        debug_auth("ORCID: selecting OAuth client configuration")
        redirect_url = settings.DEFAULT_FRONTEND_REDIRECT_URL
        if client_ts_id and client_ts_id == "general":
            redirect_url = settings.GENERAL_FRONTEND_REDIRECT_URL
        elif client_ts_id and client_ts_id == "nfdi4chem":
            redirect_url = settings.NFDI4CHEM_FRONTEND_REDIRECT_URL
        elif client_ts_id and client_ts_id == "nfdi4ing":
            redirect_url = settings.NFDI4ING_FRONTEND_REDIRECT_URL
        data = {
            "code": code,
            "client_id": settings.ORCID_CLIENT_ID,
            "client_secret": settings.ORCID_CLIENT_SECRET,
            "redirect_uri": redirect_url,
            "grant_type": "authorization_code",
        }
        if code_verifier:
            data["code_verifier"] = code_verifier
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        debug_auth("ORCID: exchanging authorization code for access token")
        resp = requests.post(settings.ORCID_TOKEN_URL, data=data, headers=headers)
        debug_auth(f"ORCID: token exchange returned HTTP {resp.status_code}")
        if resp.status_code == 200:
            debug_auth("ORCID: decoding token response")
            resp = resp.json()
            user_info = {}
            user_info["token"] = resp.get("access_token")
            user_info["name"] = resp.get("name")
            user_info["orcid_id"] = resp.get("orcid")
            user_info["ts_username"] = "orcid_" + resp.get("orcid")
            debug_auth("ORCID: provider authentication succeeded")
            return user_info

        debug_auth("ORCID: provider authentication rejected (token or profile response invalid)")
        return False

    @staticmethod
    def login_valid(user_auth_token, orcid_id):
        debug_auth("ORCID: validating existing provider login")
        if not user_auth_token or user_auth_token == "":
            debug_auth("ORCID: login validation rejected; provider token missing")
            return False

        if not orcid_id or orcid_id == "":
            debug_auth("ORCID: login validation rejected; ORCID ID missing")
            return False

        url = settings.ORCID_READ_RECORD_BASE_URL + "/" + orcid_id + "/record"
        debug_auth("ORCID: requesting provider login validation")
        response = requests.get(
            url, headers={"Authorization": "Bearer " + user_auth_token}
        )
        debug_auth(f"ORCID: login validation returned HTTP {response.status_code}")
        if response.status_code == 200:
            debug_auth("ORCID: provider login valid")
            return True
        debug_auth("ORCID: provider login rejected")
        return False
