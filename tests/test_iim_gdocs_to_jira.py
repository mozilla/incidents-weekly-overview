# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from pathlib import Path

import pytest
import requests
import responses as responses_lib

from iim_gdocs_to_jira import (
    extract_datestamp,
    extract_jira_issue,
    get_issue_data,
    md_to_dict,
    metadata_table_to_dict,
    update_jira_issue_data,
    update_jira_issue_status,
)


REPORTS_DIR = Path(__file__).parent / "data"

JIRA_BASE_URL = "https://jira.example.com"
USERNAME = "user"
PASSWORD = "pass"


@pytest.fixture
def merino_md():
    return (REPORTS_DIR / "iim_131_service_alpha.md").read_text()


@pytest.fixture
def autopush_md():
    return (REPORTS_DIR / "iim_133_bravoservice.md").read_text()


# ---------------------------------------------------------------------------
# extract_jira_issue
# ---------------------------------------------------------------------------


def test_extract_jira_issue_link():
    assert extract_jira_issue("[IIM-131](https://jira.example.com/browse/IIM-131)") == "IIM-131"


def test_extract_jira_issue_bare_key():
    assert extract_jira_issue("IIM-42") == "IIM-42"


def test_extract_jira_issue_no_key():
    with pytest.raises(Exception):
        extract_jira_issue("no jira issue here")


# ---------------------------------------------------------------------------
# extract_datestamp
# ---------------------------------------------------------------------------


def test_extract_datestamp_datetime():
    assert extract_datestamp("2026-02-21 08:57") == "2026-02-21T08:57:00.000-0000"


def test_extract_datestamp_date_only():
    assert extract_datestamp("2026-02-21") == "2026-02-21T00:00:00.000-0000"


def test_extract_datestamp_no_match():
    assert extract_datestamp("no date here") is None


# ---------------------------------------------------------------------------
# md_to_dict
# ---------------------------------------------------------------------------


def test_md_to_dict_merino(merino_md):
    data = md_to_dict(merino_md)
    assert data["key"] == "IIM-131"
    assert data["severity"] == {"value": "S2"}
    assert data["detection method"] == {"value": "Manual"}
    assert data["status"] == "Mitigated"
    assert data["impact start"] is not None
    assert data["detected"] is not None
    assert data["mitigated"] is not None


def test_md_to_dict_autopush(autopush_md):
    data = md_to_dict(autopush_md)
    assert data["key"] == "IIM-133"
    assert data["severity"] == {"value": "S3"}
    assert data["detection method"] == {"value": "Automation"}
    assert data["status"] == "Mitigated"


# ---------------------------------------------------------------------------
# metadata_table_to_dict
# ---------------------------------------------------------------------------


SAMPLE_TABLE = """\
| Incident Severity | S2 - High |
| :---- | :---- |
| **Incident Title** | Test incident |
| **Jira Ticket/Bug Number** | [IIM-99](https://jira.example.com/browse/IIM-99) |
| **Time of first Impact** | 2026-01-01 10:00 |
| **Time Detected** | 2026-01-01 10:05 |
| **Time Alerted** | 2026-01-01 10:06 |
| **Time Acknowledged** | 2026-01-01 10:07 |
| **Time Responded/Engaged** | 2026-01-01 10:08 |
| **Time Mitigated (Repaired)** | 2026-01-01 11:00 |
| **Time Resolved** | 2026-01-01 12:00 |
| **Issue detected via** | Manual/Human |
| **Current Status** | Mitigated |
"""


def test_metadata_table_to_dict_happy():
    data = metadata_table_to_dict(SAMPLE_TABLE)
    assert data["key"] == "IIM-99"
    assert data["severity"] == {"value": "S2"}
    assert data["status"] == "Mitigated"
    assert data["detection method"] == {"value": "Manual"}
    assert data["impact start"] == "2026-01-01T10:00:00.000-0000"
    assert data["mitigated"] == "2026-01-01T11:00:00.000-0000"
    assert data["resolved"] == "2026-01-01T12:00:00.000-0000"


# ---------------------------------------------------------------------------
# get_issue_data
# ---------------------------------------------------------------------------


@responses_lib.activate
def test_get_issue_data_happy():
    issue_data = {"key": "IIM-131", "fields": {"status": {"name": "Mitigated"}}}
    responses_lib.add(
        responses_lib.GET,
        f"{JIRA_BASE_URL}/rest/api/3/issue/IIM-131",
        json=issue_data,
        status=200,
    )

    result = get_issue_data(JIRA_BASE_URL, USERNAME, PASSWORD, "IIM-131")
    assert result == issue_data


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
