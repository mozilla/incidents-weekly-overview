# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from pathlib import Path

import pytest
import requests
import responses as responses_lib

from iim.iim_gdocs_to_jira import (
    InvalidIncidentReport,
    generate_actions_diff,
    generate_metadata_diff,
    generate_status_diff,
    read_markdown,
)
from iim.libreport import ActionItem, IncidentReport


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
    path = REPORTS_DIR / "2026_03_13_test_report_v20260312.md"
    content = read_markdown(str(path))
    assert content == path.read_text()


def test_read_markdown_incident_not_at_top():
    # incident_service_alpha has instruction text before the # Incident heading
    path = REPORTS_DIR / "incident_service_alpha_v20250520.md"
    content = read_markdown(str(path))
    assert content == path.read_text()


def test_read_markdown_not_an_incident_report(tmp_path):
    path = tmp_path / "not_an_incident.md"
    path.write_text("# Some Other Document\n\nSome content.\n")
    with pytest.raises(InvalidIncidentReport):
        read_markdown(str(path))


# ---------------------------------------------------------------------------
# generate_metadata_diff
# ---------------------------------------------------------------------------


def test_generate_metadata_diff_no_changes():
    # generate_metadata_diff appends declare_date to report_data.summary, so
    # jira_data.summary must already include it while report_data.summary must
    # be the bare title
    jira_data = IncidentReport(
        key="IIM-1",
        summary="Test incident (2026-01-01)",
        declare_date="2026-01-01",
        severity="S2",
    )
    report_data = IncidentReport(
        key="IIM-1",
        summary="Test incident",
        declare_date="2026-01-01",
        severity="S2",
    )
    diff = generate_metadata_diff(jira_data=jira_data, report_data=report_data)
    assert all(d.old_value == d.new_value for d in diff)


def test_generate_metadata_diff_summary_appends_declare_date():
    jira_data = IncidentReport(
        key="IIM-1", summary="Test incident", declare_date="2026-01-01"
    )
    report_data = IncidentReport(
        key="IIM-1", summary="Test incident", declare_date="2026-01-01"
    )
    diff = generate_metadata_diff(jira_data=jira_data, report_data=report_data)
    summary_diff = next(d for d in diff if d.name == "summary")
    assert summary_diff.new_value == "Test incident (2026-01-01)"


def test_generate_metadata_diff_summary_falls_back_to_jira_declare_date():
    jira_data = IncidentReport(
        key="IIM-1", summary="Test incident", declare_date="2026-01-01"
    )
    report_data = IncidentReport(
        key="IIM-1", summary="Test incident", declare_date=None
    )
    diff = generate_metadata_diff(jira_data=jira_data, report_data=report_data)
    summary_diff = next(d for d in diff if d.name == "summary")
    assert summary_diff.new_value == "Test incident (2026-01-01)"


# ---------------------------------------------------------------------------
# generate_status_diff
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "jira_status, report_status",
    [
        ("Mitigated", "Mitigated"),
        ("Mitigated", "Resolved"),
    ],
)
def test_generate_status_diff(jira_status, report_status):
    jira_data = IncidentReport(key="IIM-1", status=jira_status)
    report_data = IncidentReport(key="IIM-1", status=report_status)
    diff = generate_status_diff(jira_data=jira_data, report_data=report_data)
    assert diff[0].name == "status"
    assert diff[0].old_value == jira_status
    assert diff[0].new_value == report_status
    assert diff[0].field_value is None
    assert diff[0].from_to is None


# ---------------------------------------------------------------------------
# generate_actions_diff
# ---------------------------------------------------------------------------

JIRA_ITEM = ActionItem(url="https://jira.example.net/browse/IIM-10", jira_id="link-1")
GH_ITEM = ActionItem(
    url="https://github.com/mozilla/firefox/issues/5", status="open", title="Fix it"
)


def test_generate_actions_diff_no_action_items():
    jira_data = IncidentReport(key="IIM-1")
    report_data = IncidentReport(key="IIM-1")
    diff = generate_actions_diff(jira_data=jira_data, report_data=report_data)
    assert diff == []


def test_generate_actions_diff_same_item_both_sides():
    jira_data = IncidentReport(key="IIM-1", action_items=[JIRA_ITEM])
    report_data = IncidentReport(key="IIM-1", action_items=[JIRA_ITEM])
    diff = generate_actions_diff(jira_data=jira_data, report_data=report_data)
    assert len(diff) == 1
    assert diff[0].old_value == diff[0].new_value == "IIM-10"


def test_generate_actions_diff_item_added():
    jira_data = IncidentReport(key="IIM-1", action_items=[])
    report_data = IncidentReport(key="IIM-1", action_items=[JIRA_ITEM])
    diff = generate_actions_diff(jira_data=jira_data, report_data=report_data)
    assert len(diff) == 1
    assert diff[0].old_value is None
    assert diff[0].new_value == "IIM-10"


def test_generate_actions_diff_item_removed():
    jira_data = IncidentReport(key="IIM-1", action_items=[JIRA_ITEM])
    report_data = IncidentReport(key="IIM-1", action_items=[])
    diff = generate_actions_diff(jira_data=jira_data, report_data=report_data)
    assert len(diff) == 1
    assert diff[0].old_value == "IIM-10"
    assert diff[0].new_value is None


def test_generate_actions_diff_from_to_contains_both_items():
    jira_data = IncidentReport(key="IIM-1", action_items=[GH_ITEM])
    report_data = IncidentReport(key="IIM-1", action_items=[GH_ITEM])
    diff = generate_actions_diff(jira_data=jira_data, report_data=report_data)
    assert diff[0].from_to == (GH_ITEM, GH_ITEM)


def test_generate_actions_diff_non_jira_item_status_changed():
    url = "https://github.com/mozilla/firefox/issues/5"
    old_item = ActionItem(url=url, status="open", title="Fix it")
    new_item = ActionItem(url=url, status="closed", title="Fix it")
    jira_data = IncidentReport(key="IIM-1", action_items=[old_item])
    report_data = IncidentReport(key="IIM-1", action_items=[new_item])
    diff = generate_actions_diff(jira_data=jira_data, report_data=report_data)
    assert len(diff) == 1
    assert diff[0].old_value == f"action: [open] {url} Fix it"
    assert diff[0].new_value == f"action: [closed] {url} Fix it"


def test_generate_actions_diff_items_without_url_ignored():
    jira_data = IncidentReport(key="IIM-1", action_items=[ActionItem(title="no url")])
    report_data = IncidentReport(key="IIM-1", action_items=[ActionItem(title="no url")])
    diff = generate_actions_diff(jira_data=jira_data, report_data=report_data)
    assert diff == []


def test_generate_actions_diff_mixed_add_and_remove():
    jira_url = "https://jira.example.net/browse/IIM-10"
    gh_url = "https://github.com/mozilla/firefox/issues/5"
    old_item = ActionItem(url=jira_url, jira_id="link-1")
    new_item = ActionItem(url=gh_url, status="open", title="Fix it")
    jira_data = IncidentReport(key="IIM-1", action_items=[old_item])
    report_data = IncidentReport(key="IIM-1", action_items=[new_item])
    diff = generate_actions_diff(jira_data=jira_data, report_data=report_data)
    assert len(diff) == 2
    removed = next(d for d in diff if d.old_value is not None and d.new_value is None)
    added = next(d for d in diff if d.old_value is None and d.new_value is not None)
    assert removed.old_value == "IIM-10"
    assert added.new_value == f"action: [open] {gh_url} Fix it"


# ---------------------------------------------------------------------------
# generate_metadata_diff — field_value correctness and None branches
# ---------------------------------------------------------------------------


def test_generate_metadata_diff_summary_field_value_key():
    jira_data = IncidentReport(
        key="IIM-1", summary="Old title", declare_date="2026-01-01"
    )
    report_data = IncidentReport(
        key="IIM-1", summary="New title", declare_date="2026-01-01"
    )
    diff = generate_metadata_diff(jira_data=jira_data, report_data=report_data)
    summary_diff = next(d for d in diff if d.name == "summary")
    assert "summary" in summary_diff.field_value
    assert summary_diff.field_value["summary"] == "New title (2026-01-01)"


def test_generate_metadata_diff_summary_not_double_appended():
    jira_data = IncidentReport(
        key="IIM-1", summary="Test incident (2026-01-01)", declare_date="2026-01-01"
    )
    report_data = IncidentReport(
        key="IIM-1", summary="Test incident (2026-01-01)", declare_date="2026-01-01"
    )
    diff = generate_metadata_diff(jira_data=jira_data, report_data=report_data)
    summary_diff = next(d for d in diff if d.name == "summary")
    assert summary_diff.new_value == "Test incident (2026-01-01)"


@pytest.mark.parametrize(
    "field_name, diff_name",
    [
        ("severity", "severity"),
        ("detection_method", "detection_method"),
    ],
)
def test_generate_metadata_diff_none_option_field_value_is_none(field_name, diff_name):
    jira_data = IncidentReport(
        key="IIM-1", summary="Test incident", **{field_name: "S2"}
    )
    report_data = IncidentReport(
        key="IIM-1", summary="Test incident", **{field_name: None}
    )
    diff = generate_metadata_diff(jira_data=jira_data, report_data=report_data)
    item = next(d for d in diff if d.name == diff_name)
    # When the new value is None the field_value dict value should be None
    assert list(item.field_value.values()) == [None]


@pytest.mark.parametrize(
    "diff_name, jira_field",
    [
        ("impact start (ts)", "customfield_18693"),
        ("alerted (ts)", "customfield_18695"),
        ("acknowledged (ts)", "customfield_18696"),
        ("responded (ts)", "customfield_18697"),
        ("mitigated (ts)", "customfield_18698"),
        ("resolved (ts)", "customfield_18699"),
    ],
)
def test_generate_metadata_diff_timestamp_field_value_keys(diff_name, jira_field):
    report_data = IncidentReport(
        key="IIM-1",
        summary="Test incident",
        impact_start="2026-01-01 10:00",
        alerted="2026-01-01 10:05",
        acknowledged="2026-01-01 10:10",
        responded="2026-01-01 10:15",
        mitigated="2026-01-01 11:00",
        resolved="2026-01-01 12:00",
    )
    diff = generate_metadata_diff(
        jira_data=IncidentReport(key="IIM-1", summary="Test incident"),
        report_data=report_data,
    )
    item = next(d for d in diff if d.name == diff_name)
    assert jira_field in item.field_value


def test_generate_metadata_diff_declared_falls_back_to_jira():
    jira_data = IncidentReport(
        key="IIM-1", summary="Test incident", declared="2026-01-01 09:00"
    )
    report_data = IncidentReport(key="IIM-1", summary="Test incident", declared=None)
    diff = generate_metadata_diff(jira_data=jira_data, report_data=report_data)
    item = next(d for d in diff if d.name == "time declared (ts)")
    assert item.new_value == "2026-01-01 09:00"


# ---------------------------------------------------------------------------
# generate_status_diff — field_value is always None
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "jira_status, report_status",
    [
        ("Mitigated", "Mitigated"),
        ("In Progress", "Resolved"),
    ],
)
def test_generate_status_diff_field_value_always_none(jira_status, report_status):
    jira_data = IncidentReport(key="IIM-1", status=jira_status)
    report_data = IncidentReport(key="IIM-1", status=report_status)
    diff = generate_status_diff(jira_data=jira_data, report_data=report_data)
    assert diff[0].field_value is None
    assert diff[0].from_to is None


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


# ---------------------------------------------------------------------------
# read_markdown — missing file
# ---------------------------------------------------------------------------


def test_read_markdown_missing_file():
    with pytest.raises(FileNotFoundError):
        read_markdown("/nonexistent/path/report.md")
