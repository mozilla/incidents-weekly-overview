# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import urllib.parse

import arrow
import pytest
import responses as responses_lib
import requests

from iim.libjira import (
    convert_datestamp,
    extract_doc,
    fix_jira_incident_data,
    generate_jira_link,
    get_all_issues_for_project,
    get_arrow_time_or_none,
)


# ---------------------------------------------------------------------------
# convert_datestamp
# ---------------------------------------------------------------------------


def test_convert_datestamp_happy():
    assert convert_datestamp("2025-01-31T15:06:00.000-0500") == "2025-01-31 15:06:00"


def test_convert_datestamp_none():
    assert convert_datestamp(None) is None


def test_convert_datestamp_empty_string():
    assert convert_datestamp("") == ""


# ---------------------------------------------------------------------------
# extract_doc
# ---------------------------------------------------------------------------

GDOC_URL = "https://docs.google.com/document/d/abc123/edit"
NON_GDOC_URL = "https://example.com/document"


def _incident_with_description(description):
    return {"fields": {"description": description}}


def test_extract_doc_inline_card():
    incident = _incident_with_description(
        {
            "content": [
                {
                    "type": "inlineCard",
                    "attrs": {"url": GDOC_URL},
                }
            ]
        }
    )
    assert extract_doc(incident) == GDOC_URL


def test_extract_doc_text_mark():
    incident = _incident_with_description(
        {
            "content": [
                {
                    "type": "text",
                    "text": "Incident report",
                    "marks": [
                        {"type": "link", "attrs": {"href": GDOC_URL}},
                    ],
                }
            ]
        }
    )
    assert extract_doc(incident) == GDOC_URL


def test_extract_doc_no_description():
    incident = {"fields": {}}
    assert extract_doc(incident) == "no doc"


def test_extract_doc_non_matching_url():
    incident = _incident_with_description(
        {
            "content": [
                {
                    "type": "inlineCard",
                    "attrs": {"url": NON_GDOC_URL},
                }
            ]
        }
    )
    assert extract_doc(incident) == "no doc"


# ---------------------------------------------------------------------------
# fix_jira_incident_data
# ---------------------------------------------------------------------------

JIRA_URL = "https://jira.example.com"


def _full_incident(gdoc_url):
    return {
        "key": "IIM-42",
        "fields": {
            "status": {"name": "Closed"},
            "summary": "Everything is on fire",
            # severity
            "customfield_10319": {"value": "S1"},
            # services
            "customfield_18555": "payments,auth",
            # declare date
            "customfield_15087": "2025-02-01T10:00:00.000+0000",
            # impact start
            "customfield_15191": "2025-02-01T09:50:00.000+0000",
            # detection method
            "customfield_12881": {"value": "Automated"},
            # detected
            "customfield_12882": "2025-02-01T09:51:00.000+0000",
            # alerted
            "customfield_12883": "2025-02-01T09:52:00.000+0000",
            # acknowledged
            "customfield_12884": "2025-02-01T09:53:00.000+0000",
            # responded
            "customfield_12885": "2025-02-01T09:54:00.000+0000",
            # mitigated
            "customfield_12886": "2025-02-01T09:55:00.000+0000",
            # resolved
            "customfield_12887": "2025-02-01T10:05:00.000+0000",
            "description": {
                "content": [
                    {
                        "type": "inlineCard",
                        "attrs": {"url": gdoc_url},
                    }
                ]
            },
        },
    }


def test_fix_jira_incident_data_happy():
    incident = _full_incident(gdoc_url=GDOC_URL)
    result = fix_jira_incident_data(jira_url=JIRA_URL, incident=incident)

    assert result["key"] == "IIM-42"
    assert result["jira_url"] == f"{JIRA_URL}/browse/IIM-42"
    assert result["status"] == "Closed"
    assert result["summary"] == "Everything is on fire"
    assert result["severity"] == "S1"
    assert result["entities"] == ["payments", "auth"]
    assert result["report_url"] == GDOC_URL
    assert result["declare date"] == "2025-02-01T10:00:00.000+0000"


def test_fix_jira_incident_data_missing_optional_fields():
    incident = {
        "key": "IIM-7",
        "fields": {
            "status": {"name": "Open"},
            "summary": "Minor wobble",
            "description": {},
        },
    }
    result = fix_jira_incident_data(jira_url=JIRA_URL, incident=incident)

    assert result["severity"] == "undetermined"
    assert result["entities"] == ["unknown"]


# ---------------------------------------------------------------------------
# get_arrow_time_or_none
# ---------------------------------------------------------------------------


def test_get_arrow_time_or_none_happy():
    incident = {
        "fields": {
            "customfield_12882": "2025-02-01T09:51:00.000+0000",
        }
    }
    result = get_arrow_time_or_none(incident, "customfield_12882", "detected")
    assert isinstance(result, arrow.Arrow)
    assert result.year == 2025


def test_get_arrow_time_or_none_missing_field():
    incident = {"fields": {}}
    result = get_arrow_time_or_none(incident, "customfield_12882", "detected")
    assert result == ""


# ---------------------------------------------------------------------------
# generate_jira_link
# ---------------------------------------------------------------------------


def test_generate_jira_link():
    keys = ["IIM-1", "IIM-2"]
    url = generate_jira_link(JIRA_URL, keys)

    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)

    assert "jql" in params
    jql = params["jql"][0]
    assert "IIM-1,IIM-2" in jql
    assert url.startswith(JIRA_URL)


# ---------------------------------------------------------------------------
# get_all_issues_for_project
# ---------------------------------------------------------------------------

API_URL = "https://jira.example.com/rest/api/3/search/jql"


@responses_lib.activate
def test_get_all_issues_single_page():
    issue = {"key": "IIM-1", "fields": {}}
    responses_lib.add(
        responses_lib.GET,
        API_URL,
        json={"issues": [issue], "isLast": True},
        status=200,
    )

    result = get_all_issues_for_project(JIRA_URL, "IIM", "user", "pass")
    assert result == [issue]
    assert len(responses_lib.calls) == 1


@responses_lib.activate
def test_get_all_issues_paginated():
    issue1 = {"key": "IIM-1", "fields": {}}
    issue2 = {"key": "IIM-2", "fields": {}}

    responses_lib.add(
        responses_lib.GET,
        API_URL,
        json={"issues": [issue1], "isLast": False, "nextPageToken": "tok123"},
        status=200,
    )
    responses_lib.add(
        responses_lib.GET,
        API_URL,
        json={"issues": [issue2], "isLast": True},
        status=200,
    )

    result = get_all_issues_for_project(JIRA_URL, "IIM", "user", "pass")
    assert result == [issue1, issue2]
    assert len(responses_lib.calls) == 2


@responses_lib.activate
def test_get_all_issues_http_error():
    responses_lib.add(
        responses_lib.GET,
        API_URL,
        json={"errorMessages": ["Unauthorized"]},
        status=401,
    )

    with pytest.raises(requests.HTTPError):
        get_all_issues_for_project(JIRA_URL, "IIM", "user", "badpass")


@responses_lib.activate
def test_get_all_issues_empty():
    responses_lib.add(
        responses_lib.GET,
        API_URL,
        json={"issues": [], "isLast": True},
        status=200,
    )

    result = get_all_issues_for_project(JIRA_URL, "IIM", "user", "pass")
    assert result == []
