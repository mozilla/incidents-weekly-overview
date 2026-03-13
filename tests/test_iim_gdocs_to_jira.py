# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import pytest
import requests
import responses as responses_lib

from iim.libjira import (
    get_issue_data,
    update_jira_issue_data,
    update_jira_issue_status,
)


JIRA_BASE_URL = "https://jira.example.com"
USERNAME = "user"
PASSWORD = "pass"


# ---------------------------------------------------------------------------
# get_issue_data
# ---------------------------------------------------------------------------


@responses_lib.activate
def test_get_issue_data_happy():
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

    result = get_issue_data(JIRA_BASE_URL, USERNAME, PASSWORD, "IIM-131")
    assert result.key == "IIM-131"
    assert result.status == "Mitigated"
    assert result.summary == "Test incident"


@responses_lib.activate
def test_get_issue_data_401():
    responses_lib.add(
        responses_lib.GET,
        f"{JIRA_BASE_URL}/rest/api/3/issue/IIM-131",
        json={"errorMessages": ["Unauthorized"]},
        status=401,
    )

    with pytest.raises(requests.HTTPError):
        get_issue_data(JIRA_BASE_URL, USERNAME, PASSWORD, "IIM-131")


# ---------------------------------------------------------------------------
# update_jira_issue_data
# ---------------------------------------------------------------------------


@responses_lib.activate
def test_update_jira_issue_data_happy():
    responses_lib.add(
        responses_lib.PUT,
        f"{JIRA_BASE_URL}/rest/api/3/issue/IIM-131",
        status=204,
    )

    # Should not raise
    update_jira_issue_data(
        JIRA_BASE_URL, USERNAME, PASSWORD, "IIM-131", {"summary": "Test"}
    )


@responses_lib.activate
def test_update_jira_issue_data_400():
    responses_lib.add(
        responses_lib.PUT,
        f"{JIRA_BASE_URL}/rest/api/3/issue/IIM-131",
        json={"errorMessages": ["Bad request"]},
        status=400,
    )

    with pytest.raises(requests.HTTPError):
        update_jira_issue_data(
            JIRA_BASE_URL, USERNAME, PASSWORD, "IIM-131", {"summary": "Test"}
        )


# ---------------------------------------------------------------------------
# update_jira_issue_status
# ---------------------------------------------------------------------------


@responses_lib.activate
def test_update_jira_issue_status_happy():
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
    update_jira_issue_status(JIRA_BASE_URL, USERNAME, PASSWORD, "IIM-131", "Mitigated")
    assert len(responses_lib.calls) == 2


@responses_lib.activate
def test_update_jira_issue_status_unknown_status():
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
        update_jira_issue_status(
            JIRA_BASE_URL, USERNAME, PASSWORD, "IIM-131", "Nonexistent"
        )


@responses_lib.activate
def test_update_jira_issue_status_get_error():
    transitions_url = f"{JIRA_BASE_URL}/rest/api/3/issue/IIM-131/transitions"
    responses_lib.add(
        responses_lib.GET,
        transitions_url,
        json={"errorMessages": ["Unauthorized"]},
        status=401,
    )

    with pytest.raises(requests.HTTPError):
        update_jira_issue_status(
            JIRA_BASE_URL, USERNAME, PASSWORD, "IIM-131", "Mitigated"
        )
