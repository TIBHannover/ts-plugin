from django.urls import path
from . import views

urlpatterns = [
   path('ping/', views.ping, name="ping"),
   path('issuelist/', views.get_issues_for_ontology, name="issuelist"),
   path('submit_issue/', views.submit_github_issue, name="submit_issue"),
   path('get_submited_issues/', views.get_submited_issues, name="get_submited_issues"),
   path('get_issue_templates/', views.get_issue_templates_for_repo, name="get_issue_templates"),
]
