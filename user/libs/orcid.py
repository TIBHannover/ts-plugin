import requests
from django.conf import settings


class OrcidLib:
    @staticmethod
    def authenticate(code, client_ts_id=None, code_verifier=None):
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

        resp = requests.post(settings.ORCID_TOKEN_URL, data=data, headers=headers)
        if resp.status_code == 200:
            resp = resp.json()
            user_info = {}
            user_info["token"] = resp.get("access_token")
            user_info["name"] = resp.get("name")
            user_info["orcid_id"] = resp.get("orcid")
            user_info["ts_username"] = "orcid_" + resp.get("orcid")
            return user_info

        return False

    @staticmethod
    def login_valid(user_auth_token, orcid_id):
        if not user_auth_token or user_auth_token == "":
            return False

        if not orcid_id or orcid_id == "":
            return False

        url = settings.ORCID_READ_RECORD_BASE_URL + "/" + orcid_id + "/record"
        response = requests.get(
            url, headers={"Authorization": "Bearer " + user_auth_token}
        )
        if response.status_code == 200:
            return True
        return False
