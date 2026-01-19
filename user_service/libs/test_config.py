from django.conf import settings
from user_service.libs.test_helpers import TestHelper


class BaseTest:
    test_ontology_id = "vibso"
    test_parent_ontology_id = "bfo"
    app_internal_base_url = ""
    github_access_token = settings.GITHUB_TEST_ACCESS_TOKEN
    orcid_access_token = settings.ORCID_TEST_ACCESS_TOKEN
    orcid_id = settings.ORCID_LOGIN_USERNAME
    test_github_username = "github_" + settings.GITHUB_LOGIN_USERNAME
    test_orcid_username = "orcid_" + settings.ORCID_LOGIN_USERNAME
    client_ts_id = "general"
    github_request_headers = {
        "Content-Type": "application/json",
        "X-TS-Auth-Provider": "github",
        "X-TS-Frontend-Id": client_ts_id,
        "X-CSRF-Token": TestHelper.generate_csrf_token(),
    }

    orcid_request_headers = {
        "Content-Type": "application/json",
        "X-TS-Auth-Provider": "orcid",
        "X-TS-Frontend-Id": client_ts_id,
        "X-CSRF-Token": TestHelper.generate_csrf_token(),
    }

    guest_request_headers = {
        "Authorization": "",
        "Content-Type": "application/json",
        "X-TS-Auth-Provider": "github",
        "X-TS-Frontend-Id": client_ts_id,
    }
