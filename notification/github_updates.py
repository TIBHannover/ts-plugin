from datetime import timedelta
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urljoin, urlsplit

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from notification.models import OntologyGitHubCache
from user_service.libs.terminology_service import TerminologyService, github_repository


CACHE_TTL = timedelta(hours=24)


def github_window_start(window_end):
    return (window_end.astimezone(ZoneInfo("Europe/Berlin")) - timedelta(days=1)).astimezone(ZoneInfo("UTC"))


def _refresh_metadata(cache, now):
    if cache.metadata_expires_at and cache.metadata_expires_at > now:
        return
    try:
        ontology = TerminologyService().fetch_ontology(cache.ontology_id)
    except requests.HTTPError as exc:
        if exc.response.status_code not in (404, 410):
            raise
        ontology = {}
    cache.metadata = {
        "title": ontology.get("title") or (ontology.get("label") or [cache.ontology_id])[0],
        "repository": github_repository(ontology),
    }
    cache.metadata_expires_at = now + CACHE_TTL
    cache.save(update_fields=["metadata", "metadata_expires_at"])


def _github_get(repository, path="", params=None):
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if settings.GITHUB_TS_USER_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.GITHUB_TS_USER_API_TOKEN}"
    url = f"https://api.github.com/repos/{repository}{path}"
    for _ in range(4):
        response = requests.get(
            url, headers=headers, params=params, timeout=20, allow_redirects=False,
        )
        if response.status_code not in (301, 302, 303, 307, 308):
            break
        location = response.headers.get("Location")
        if not location:
            raise ValueError("Missing GitHub redirect location")
        url = urljoin(url, location)
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc.lower() != "api.github.com":
            raise ValueError("Invalid GitHub redirect")
        if parsed.query:
            params = None
    if response.status_code != 200:
        response.raise_for_status()
        raise ValueError("Unexpected GitHub response")
    return response


def _github_items(repository, path, params):
    page = 1
    while True:
        try:
            response = _github_get(repository, path, {**params, "per_page": 100, "page": page})
        except requests.HTTPError as exc:
            if (path == "/issues" and exc.response.status_code == 410
                    or path == "/commits" and exc.response.status_code == 409):
                return
            raise
        items = response.json()
        if not isinstance(items, list):
            raise ValueError("Invalid GitHub activity response")
        yield from items
        if "next" not in response.links:
            return
        page += 1


def fetch_github_updates(repository, window_end):
    start = github_window_start(window_end)
    since, until = start.isoformat(), window_end.isoformat()
    issues = []
    for issue in _github_items(repository, "/issues", {
        "state": "all", "since": since, "sort": "created", "direction": "desc",
    }):
        created = datetime.fromisoformat(issue["created_at"].replace("Z", "+00:00"))
        if "pull_request" not in issue and start <= created < window_end:
            issues.append({"title": issue["title"], "url": issue["html_url"]})
    repo = _github_get(repository).json()
    branch = repo.get("default_branch")
    if branch not in ("main", "master"):
        branch = None
        for candidate in ("main", "master"):
            try:
                _github_get(repository, f"/branches/{candidate}")
                branch = candidate
                break
            except requests.HTTPError as exc:
                if exc.response.status_code != 404:
                    raise
    commits = []
    if branch in ("main", "master"):
        for commit in _github_items(repository, "/commits", {"sha": branch, "since": since, "until": until}):
            created = datetime.fromisoformat(commit["commit"]["committer"]["date"].replace("Z", "+00:00"))
            if start <= created < window_end:
                commits.append({
                    "title": (commit["commit"]["message"].strip() or commit["sha"]).splitlines()[0],
                    "url": commit["html_url"],
                })
    return {"issues": issues, "commits": commits, "branch": branch}


@transaction.atomic
def ontology_github_updates(ontology_id, window_end):
    OntologyGitHubCache.objects.get_or_create(ontology_id=ontology_id)
    cache = OntologyGitHubCache.objects.select_for_update().get(ontology_id=ontology_id)
    now = timezone.now()
    if cache.updates_expires_at and cache.updates_expires_at > now and cache.window_end == window_end:
        return cache.metadata, cache.updates
    _refresh_metadata(cache, now)
    repository = cache.metadata["repository"]
    updates = {"issues": [], "commits": []}
    if repository:
        try:
            updates = fetch_github_updates(repository, window_end)
        except requests.HTTPError as exc:
            if exc.response.status_code not in (404, 410):
                raise
    cache.updates = updates
    cache.updates_expires_at = now + CACHE_TTL
    cache.window_end = window_end
    cache.save(update_fields=["updates", "updates_expires_at", "window_end"])
    return cache.metadata, updates
