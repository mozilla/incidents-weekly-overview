# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from pathlib import Path

import pytest
import requests
import responses as responses_lib

from iim.iim_gdocs_to_jira import (
    InvalidIncidentReport,
    read_markdown,
)


JIRA_BASE_URL = "https://jira.example.com"
USERNAME = "user"
PASSWORD = "pass"


# ---------------------------------------------------------------------------
# get_issue_report
# ---------------------------------------------------------------------------


@responses_lib.activate
def test_get_issue_report_happy(jira_client):
    issue_data = {
        "key": "IIM-131",
        "fields": {
            "status": {"name": "Mitigated"},
            "summary": "Test incident",
            "description": {},
        },
    }
    responses_lib.add(
        responses_lib.GET,
        f"{JIRA_BASE_URL}/rest/api/3/issue/IIM-131",
        json=issue_data,
        status=200,
    )
    responses_lib.add(
        responses_lib.GET,
        f"{JIRA_BASE_URL}/rest/api/3/issue/IIM-131/remotelink",
        json=[],
        status=200,
    )

    result = jira_client.get_issue_report("IIM-131")
    assert result.key == "IIM-131"
    assert result.status == "Mitigated"
    assert result.summary == "Test incident"


@responses_lib.activate
def test_get_issue_report_401(jira_client):
    responses_lib.add(
        responses_lib.GET,
        f"{JIRA_BASE_URL}/rest/api/3/issue/IIM-131",
        json={"errorMessages": ["Unauthorized"]},
        status=401,
    )

    with pytest.raises(requests.HTTPError):
        jira_client.get_issue_report("IIM-131")


# ---------------------------------------------------------------------------
# update_issue_data
# ---------------------------------------------------------------------------


@responses_lib.activate
def test_update_issue_data_happy(jira_client):
    responses_lib.add(
        responses_lib.PUT,
        f"{JIRA_BASE_URL}/rest/api/3/issue/IIM-131",
        status=204,
    )

    # Should not raise
    jira_client.update_issue_data("IIM-131", {"summary": "Test"})


@responses_lib.activate
def test_update_issue_data_400(jira_client):
    responses_lib.add(
        responses_lib.PUT,
        f"{JIRA_BASE_URL}/rest/api/3/issue/IIM-131",
        json={"errorMessages": ["Bad request"]},
        status=400,
    )

    with pytest.raises(requests.HTTPError):
        jira_client.update_issue_data("IIM-131", {"summary": "Test"})


# ---------------------------------------------------------------------------
# update_issue_status
# ---------------------------------------------------------------------------


@responses_lib.activate
def test_update_issue_status_happy(jira_client):
    transitions_url = f"{JIRA_BASE_URL}/rest/api/3/issue/IIM-131/transitions"
    responses_lib.add(
        responses_lib.GET,
        transitions_url,
        json={
            "transitions": [
                {"id": "10", "to": {"name": "Mitigated"}},
                {"id": "20", "to": {"name": "Resolved"}},
            ]
        },
        status=200,
    )
    responses_lib.add(
        responses_lib.POST,
        transitions_url,
        status=204,
    )

    # Should not raise
    jira_client.update_issue_status("IIM-131", "Mitigated")
    assert len(responses_lib.calls) == 2


@responses_lib.activate
def test_update_issue_status_unknown_status(jira_client):
    transitions_url = f"{JIRA_BASE_URL}/rest/api/3/issue/IIM-131/transitions"
    responses_lib.add(
        responses_lib.GET,
        transitions_url,
        json={
            "transitions": [
                {"id": "10", "to": {"name": "Mitigated"}},
                {"id": "20", "to": {"name": "Resolved"}},
            ]
        },
        status=200,
    )

    with pytest.raises(ValueError, match="Available transitions"):
        jira_client.update_issue_status("IIM-131", "Nonexistent")


@responses_lib.activate
def test_update_issue_status_get_error(jira_client):
    transitions_url = f"{JIRA_BASE_URL}/rest/api/3/issue/IIM-131/transitions"
    responses_lib.add(
        responses_lib.GET,
        transitions_url,
        json={"errorMessages": ["Unauthorized"]},
        status=401,
    )

    with pytest.raises(requests.HTTPError):
        jira_client.update_issue_status("IIM-131", "Mitigated")


# ---------------------------------------------------------------------------
# read_markdown
# ---------------------------------------------------------------------------


REPORTS_DIR = Path(__file__).parent / "data"


def test_read_markdown_incident_at_top():
    path = REPORTS_DIR / "20260312" / "incident_testreport.md"
    content = read_markdown(str(path))
    assert content == path.read_text()


def test_read_markdown_incident_not_at_top():
    # incident_service_alpha has instruction text before the # Incident heading
    path = REPORTS_DIR / "20250520" / "incident_service_alpha.md"
    content = read_markdown(str(path))
    assert content == path.read_text()


def test_read_markdown_not_an_incident_report(tmp_path):
    path = tmp_path / "not_an_incident.md"
    path.write_text("# Some Other Document\n\nSome content.\n")
    with pytest.raises(InvalidIncidentReport):
        read_markdown(str(path))


def test_read_markdown_missing_file():
    with pytest.raises(FileNotFoundError):
        read_markdown("/nonexistent/path/report.md")


# ---------------------------------------------------------------------------
# get_issue_report — remote links parsing
# ---------------------------------------------------------------------------


@responses_lib.activate
def test_get_issue_report_remote_links_action_items_parsed(jira_client):
    issue_data = {
        "key": "IIM-131",
        "fields": {
            "status": {"name": "In Progress"},
            "summary": "Test incident",
            "description": {},
        },
    }
    gh_url = "https://github.com/mozilla/firefox/issues/5"
    remote_links = [
        {
            "id": 42,
            "object": {
                "url": gh_url,
                "title": f"action: [open] {gh_url} Fix it",
            },
        }
    ]
    responses_lib.add(
        responses_lib.GET,
        f"{JIRA_BASE_URL}/rest/api/3/issue/IIM-131",
        json=issue_data,
        status=200,
    )
    responses_lib.add(
        responses_lib.GET,
        f"{JIRA_BASE_URL}/rest/api/3/issue/IIM-131/remotelink",
        json=remote_links,
        status=200,
    )

    result = jira_client.get_issue_report("IIM-131")
    assert len(result.action_items) == 1
    item = result.action_items[0]
    assert item.url == gh_url
    assert item.status == "open"
    assert item.title == "Fix it"
    assert item.jira_id == "42"


@responses_lib.activate
def test_get_issue_report_remote_links_non_action_ignored(jira_client):
    issue_data = {
        "key": "IIM-131",
        "fields": {
            "status": {"name": "In Progress"},
            "summary": "Test incident",
            "description": {},
        },
    }
    remote_links = [
        {
            "id": 99,
            "object": {
                "url": "https://example.com/some-doc",
                "title": "Some related document",
            },
        }
    ]
    responses_lib.add(
        responses_lib.GET,
        f"{JIRA_BASE_URL}/rest/api/3/issue/IIM-131",
        json=issue_data,
        status=200,
    )
    responses_lib.add(
        responses_lib.GET,
        f"{JIRA_BASE_URL}/rest/api/3/issue/IIM-131/remotelink",
        json=remote_links,
        status=200,
    )

    result = jira_client.get_issue_report("IIM-131")
    assert result.action_items == []
