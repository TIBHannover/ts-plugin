from django.conf import settings
 
class BaseTest:

    test_ontology_id = "vibso"
    test_parent_ontology_id = "bfo" 
    app_internal_base_url = ""             
    github_access_token = settings.GITHUB_TEST_ACCESS_TOKEN
    orcid_access_token = settings.ORCID_TEST_ACCESS_TOKEN
    orcid_id = settings.ORCID_LOGIN_USERNAME
    test_github_username = "github_" + settings.GITHUB_LOGIN_USERNAME
    test_github_user_ts_token = settings.GITHUB_USER_TS_TOKEN
    test_orcid_username = "orcid_" + settings.ORCID_LOGIN_USERNAME
    test_orcid_user_ts_token = settings.ORCID_USER_TS_TOKEN
    client_ts_id = "general"
    client_ts_token = settings.FRONTEDN_AUTH_TOKEN
    github_request_headers = {
        "Authorization": github_access_token,
        "Content-Type": "application/json",
        "X-TS-Auth-Provider": "github",             
        "X-TS-Frontend-Id": client_ts_id,
        "X-TS-Frontend-Token": client_ts_token,
        "X-TS-User-Name": test_github_username,
        "X-TS-User-Token": test_github_user_ts_token
    }

    orcid_request_headers = {
        "Authorization": orcid_access_token, 
        "Content-Type": "application/json",                 
        "X-TS-Orcid-Id": orcid_id,
        "X-TS-Auth-Provider": "orcid",
        "X-TS-Frontend-Id": client_ts_id,
        "X-TS-Frontend-Token": client_ts_token,
        "X-TS-User-Name": test_orcid_username,
        "X-TS-User-Token": test_orcid_user_ts_token
    }

    
    guest_request_headers = {
        "Authorization": "",
        "Content-Type": "application/json",
        "X-TS-Auth-Provider": "github",             
        "X-TS-Frontend-Id": client_ts_id,
        "X-TS-Frontend-Token": client_ts_token,
        "X-TS-User-Name": test_github_username,
        "X-TS-User-Token": "",            
    }





