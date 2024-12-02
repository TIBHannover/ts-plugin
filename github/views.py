from user.libs.github import GithubLib
from github.models import GithubIssueRequestModel
from user.models import UserModel
import requests
from datetime import datetime as _time
from user_service.libs.decorators import (
    error_handler_decorator, 
    authentication_required, 
    client_id_validation
)
import urllib.parse as url_parser
from django.views.decorators.http import  require_http_methods
from user_service.middlewares.request import (get_headers_dict, 
    get_client_id_from_request, 
    get_username_from_request
)
from user_service.libs.utils import create_json_response
from django.conf import settings
import json
from django.http import HttpResponseBadRequest, HttpResponseServerError




@require_http_methods["GET"]
def ping(request):
    return create_json_response({"response": "Pong"})



@error_handler_decorator
@client_id_validation
@require_http_methods['GET']
def get_issues_for_ontology(request):
    args = request.GET
    issue_path = args.get('path')
    issue_path = url_parser.unquote(issue_path)
    issue_state = args.get('state')
    issue_type = args.get('type')
    if issue_type == "pr":
        issue_path = issue_path.replace("/issues", "/pulls")    
    page_size = args.get('size')
    page_number = args.get('page')
    url = settings.GITHUB_REPOS_URL + issue_path + "?state={state}&per_page={size}&page={page}"
    url = url.format(state=issue_state, size=page_size, page=page_number)    
    headers = GithubLib.create_github_request_header()
    resp = requests.get(url, headers=headers)        
    if resp.status_code == 200:
        issues = resp.json()
        issues_list = []
        for issue in issues:
            if issue_type == "pr" or (issue_type == "issue" and "pull_request" not in issue.keys()):
                issue = GithubLib.get_labels_for_issue(issue=issue)
                issues_list.append(issue)
                                                                
        return create_json_response({'issues': issues_list})            
    
    return create_json_response({'issues': []})
    




@error_handler_decorator
@authentication_required
@require_http_methods['POST']
def submit_github_issue(request):
    request_header = get_headers_dict()
    if request_header.get('auth_provider') != 'github':
        return create_json_response({'error': "Only github users can use this feature"})
    
    _form = json.loads(request.body)
    frontend_id = get_client_id_from_request()
    issue_title = _form["title"]
    issue_content = _form["content"]
    issue_creator_url = _form['repo_url']
    if issue_creator_url[len(issue_creator_url) - 1] == '/':
        issue_creator_url += 'issues'
    else:
        issue_creator_url += '/issues'
    ontology_id = _form['ontology_id']
    username = get_username_from_request()
    issue_type = _form['issueType']
    user = UserModel.objects.filter(username=username).first()
    github_issue_db_entry = {
        "user_id": user.id,
        "created_at": _time.now(),
        "ontology_id": ontology_id,
        "issue_content": issue_content,
        "issue_title": issue_title,
        "issue_url": "",
        "client_ts": frontend_id,
        "issue_type": issue_type
    }
    github_issue_record = GithubIssueRequestModel(**github_issue_db_entry)
    if "https://github.com/" not in issue_creator_url:
        return HttpResponseBadRequest("Ontology is not hosted on Github")

    issue_creator_url = "https://api.github.com/repos/" + issue_creator_url.split("https://github.com/")[1]     
    payload = {"title": issue_title, "body":issue_content}
    user_auth_token = request.headers.get("Authorization")
    headers = GithubLib.create_github_request_header(user_access_token=user_auth_token)
    resp = requests.post(issue_creator_url, json=payload, headers=headers)        
    if resp.status_code == 201:            
        json_result = resp.json()                    
        new_issue_url = json_result.get("html_url")
        github_issue_record.issue_url = new_issue_url
        github_issue_record.create_record()            
        return create_json_response({'new_issue_url': new_issue_url})
    
    return HttpResponseServerError("Something went wrong.")




@error_handler_decorator
@authentication_required
@require_http_methods['GET']
def get_submited_issues(request):
    request_header = get_headers_dict()
    if request_header.get('auth_provider') != 'github':
        return create_json_response({'error': "Only github users can use this feature"})


    username = get_username_from_request()
    user = UserModel.objects.filter(username=username).first()
    issuesList = user.user_github_issues.all()
    return create_json_response({'submited_issues': [issue.to_dict() for issue in issuesList]})





@error_handler_decorator
@authentication_required
@require_http_methods['POST']
def get_issue_templates_for_repo(request):    
    request_header = get_headers_dict()
    if request_header.get('auth_provider') != 'github':
        return create_json_response({'error': "Only github users can use this feature"})
   
    _form = json.loads(request.body)
    repo_url = _form["repo_url"]
    if "https://github.com/" not in repo_url:
        return HttpResponseBadRequest("Ontology is not hosted on Github")

    templates_url = "https://api.github.com/repos/" + repo_url.split("https://github.com/")[1]
    template_path = '/contents/.github/ISSUE_TEMPLATE'
    if templates_url[len(templates_url) - 1] == '/':
        template_path = 'contents/.github/ISSUE_TEMPLATE'
    templates_url = templates_url.strip() + template_path
    headers = GithubLib.create_github_request_header()
    resp = requests.get(templates_url, headers=headers)        
    if resp.status_code == 200:
        templates = []
        for temp in resp.json():
            node = {}
            node['template_name'] = temp['name']
            node['template_url'] = temp['download_url']
            templates.append(node)
        return create_json_response({'templates': templates})
    
    return create_json_response({'templates': []})



