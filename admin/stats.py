from note.models import NoteModel
from report.models import ReportModel
from github.models import GithubIssueRequestModel
from django.conf import settings
import urllib.parse
import requests
from user.models import UserModel
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST


class StatsShape:
    def __init__(self):
        self.note_count = 0
        self.comment_count = 0
        self.collection_count = 0
        self.termset_count = 0
        self.report_count = 0
        self.github_issues_count = 0
        self.term_request_count = 0
        self.ontology_suggestion_count = 0
        self.contact_form_count = 0

    def to_dict(self):
        return {
            "note_count": self.note_count,
            "comment_count": self.comment_count,
            "collection_count": self.collection_count,
            "termset_count": self.termset_count,
            "report_count": self.report_count,
            "github_issues_count": self.github_issues_count,
            "term_request_count": self.term_request_count,
            "ontology_suggestion_count": self.ontology_suggestion_count,
            "contact_form_count": self.contact_form_count,
        }


class Stats:
    def __init__(self):
        self.stats_gauge = Gauge(
            "app_stat_value",
            "TS-Plugin service stats",
            ["key"],
        )
        self.projects = ["nfdi4chem", "general", "nfdi4ing"]
        self.stats = {
            "nfdi4chem": StatsShape(),
            "general": StatsShape(),
            "nfdi4ing": StatsShape(),
        }

    def run(self):
        for project_id in self.projects:
            self.__calculate_stats(project_id)
            self.__calculate_gitlab_stats(project_id)
            self.stats[project_id] = self.stats[project_id].to_dict()

        for key, value in self.__flatten_stats(self.stats):
            self.stats_gauge.labels(key=key).set(value)

    def __calculate_stats(self, client_ts):
        users = UserModel.objects.filter(client_ts=client_ts).all()
        self.stats[client_ts].note_count = len(users)
        note_count = 0
        comment_count = 0
        collection_count = 0
        termset_count = 0
        report_count = 0
        github_issues_count = 0
        term_request_count = 0
        for u in users:
            user_notes = NoteModel.objects.filter(creator=u).all()
            note_count += len(user_notes)
            comment_count += len(u.user_comments.all())
            collection_count += len(u.user_collections.all())
            termset_count += len(u.user_term_sets.all())
            report_count += len(ReportModel.objects.filter(reporter=u).all())
            github_issues = GithubIssueRequestModel.objects.filter(user=u).all()
            for gi in github_issues:
                if gi.issue_type == "termRequest":
                    term_request_count += 1
                else:
                    github_issues_count += 1

        self.stats[client_ts].note_count = note_count
        self.stats[client_ts].comment_count = comment_count
        self.stats[client_ts].collection_count = collection_count
        self.stats[client_ts].termset_count = termset_count
        self.stats[client_ts].report_count = report_count
        self.stats[client_ts].github_issues_count = github_issues_count
        self.stats[client_ts].term_request_count = term_request_count

    def __calculate_gitlab_stats(self, client_ts):
        # ontology suggestion and contact form
        url = settings.GITLAB_API_BASE_URL + "{}/issues".format(
            urllib.parse.quote(settings.ONTOLOGY_SUGGESTION_REPO, safe="")
        )

        headers = {
            "PRIVATE-TOKEN": settings.GITLAB_TS_USER_API_TOKEN,
            "Content-Type": "application/json",
        }
        resp = requests.get(url, headers=headers)
        ontology_suggestion_count = 0
        for iss in resp.json():
            if client_ts == "general" and "ontology_suggestion" in iss["labels"]:
                ontology_suggestion_count += 1
            elif (
                "ontology_suggestion" in iss["labels"]
                and client_ts.upper() in iss["labels"]
            ):
                ontology_suggestion_count += 1
        self.stats[client_ts].ontology_suggestion_count = ontology_suggestion_count

        url = settings.GITLAB_API_BASE_URL + "{}/issues".format(
            urllib.parse.quote(settings.CONTACT_REQUEST_RECEIVER_REPO, safe="")
        )
        resp = requests.get(url, headers=headers)
        contact_form_count = 0
        for iss in resp.json():
            if client_ts in iss["labels"]:
                contact_form_count += 1

        self.stats[client_ts].contact_form_count = contact_form_count

    def __flatten_stats(self, data, prefix=""):
        for key, value in data.items():
            name = f"{prefix}_{key}" if prefix else key

            if isinstance(value, dict):
                yield from self.__flatten_stats(value, name)
            elif isinstance(value, (int, float)):
                yield name, value
