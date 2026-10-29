import requests
from django.conf import settings
from user.libs.auth_debug import debug_auth


class GithubLib:
    @staticmethod
    def authenticate(code, client_ts_id=None, code_verifier=None):
        client_id = settings.DEFAULT_GITHUB_CLIENT_ID
        client_secret = settings.DEFAULT_GITHUB_CLIENT_SECRET
        debug_auth("GitHub: selecting OAuth client configuration")
        redirect_url = settings.DEFAULT_FRONTEND_REDIRECT_URL
        if client_ts_id and client_ts_id == "general":
            client_id = settings.GENERAL_GITHUB_CLIENT_ID
            client_secret = settings.GENERAL_GITHUB_CLIENT_SECRET
            redirect_url = settings.GENERAL_FRONTEND_REDIRECT_URL
        elif client_ts_id and client_ts_id == "nfdi4chem":
            client_id = settings.NFDI4CHEM_GITHUB_CLIENT_ID
            client_secret = settings.NFDI4CHEM_GITHUB_CLIENT_SECRET
            redirect_url = settings.NFDI4CHEM_FRONTEND_REDIRECT_URL
        elif client_ts_id and client_ts_id == "nfdi4ing":
            client_id = settings.NFDI4ING_GITHUB_CLIENT_ID
            client_secret = settings.NFDI4ING_GITHUB_CLIENT_SECRET
            redirect_url = settings.NFDI4ING_FRONTEND_REDIRECT_URL

        data = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_url,
        }
        if code_verifier:
            data["code_verifier"] = code_verifier
        debug_auth("GitHub: exchanging authorization code for access token")
        resp = requests.post(settings.GITHUB_TOKEN_URL, data=data)
        debug_auth(f"GitHub: token exchange returned HTTP {resp.status_code}")
        if resp.status_code == 200 and "access_token=" in resp.text:
            debug_auth("GitHub: extracting access token from response")
            token = resp.text.split("access_token=")[1]
            token = token.split("&")[0]
            debug_auth("GitHub: requesting user profile")
            user = requests.get(
                settings.GITHUB_USER_URL,
                headers={"Authorization": "token " + token},
            )
            debug_auth(f"GitHub: user profile returned HTTP {user.status_code}")
            if user.status_code == 200:
                debug_auth("GitHub: decoding user profile")
                user_data = user.json()
                response_data = {}
                response_data["name"] = user_data.get("login")
                response_data["company"] = user_data.get("company")
                response_data["github_home"] = user_data.get("html_url")
                response_data["token"] = token
                response_data["login"] = user_data.get("login")
                response_data["ts_username"] = "github_" + user_data.get("login")
                debug_auth("GitHub: provider authentication succeeded")
                return response_data

        debug_auth("GitHub: provider authentication rejected (token or profile response invalid)")
        return False

    @staticmethod
    def login_valid(user_auth_token):
        debug_auth("GitHub: validating existing provider login")
        if not user_auth_token:
            debug_auth("GitHub: login validation rejected; provider token missing")
            return False
        debug_auth("GitHub: requesting provider login validation")
        user = requests.get(
            settings.GITHUB_USER_URL,
            headers={"Authorization": "token " + user_auth_token},
        )
        debug_auth(f"GitHub: login validation returned HTTP {user.status_code}")
        if user.status_code == 200 and user.json().get("login"):
            debug_auth("GitHub: provider login valid")
            return True
        debug_auth("GitHub: provider login rejected")
        return False

    @staticmethod
    def create_github_request_header(user_access_token=None):
        if not user_access_token:
            user_access_token = settings.GITHUB_TS_USER_API_TOKEN
        headers = {
            "Authorization": "Bearer " + user_access_token,
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        return headers

    @staticmethod
    def get_labels_for_issue(issue):
        try:
            issue_url = issue["labels_url"].split("{/name}")[0]
            headers = GithubLib.create_github_request_header()
            resp_labels = requests.get(issue_url, headers=headers)
            if resp_labels.status_code == 200:
                labels = resp_labels.json()
                issue["labels"] = labels
            else:
                issue["labels"] = []

            return issue
        except:
            issue["labels"] = []
            return issue
