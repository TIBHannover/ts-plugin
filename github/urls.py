from django.urls import path
from . import views
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
   path('ping/', views.ping, name="ping"),
   path('issuelist/', views.get_issues_for_ontology, name="issuelist"),
   path('submit_issue/', csrf_exempt(views.submit_github_issue), name="submit_issue"),
   path('get_submited_issues/', views.get_submited_issues, name="get_submited_issues"),
   path('get_issue_templates/', csrf_exempt(views.get_issue_templates_for_repo), name="get_issue_templates"),
]
