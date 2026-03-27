# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import pytest

from iim.libreport import ActionItem, IncidentReport, bugzilla_id, github_id, jira_key


# ---------------------------------------------------------------------------
# jira_key
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://jira.example.net/browse/IIM-42", "IIM-42"),
        ("https://jira.example.net/browse/PROJ-123", "PROJ-123"),
        ("IIM-42", "IIM-42"),
        ("PROJ-123", "PROJ-123"),
        ("https://example.com/not/a/jira/url", None),
        ("", None),
        (None, None),
    ],
)
def test_jira_key(url, expected):
    assert jira_key(url) == expected


# ---------------------------------------------------------------------------
# github_id
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url, expected",
    [
        (
            "https://github.com/mozilla/firefox/issues/99",
            "mozilla/firefox/issues/99",
        ),
        (
            "https://github.com/mozilla/firefox/pull/42",
            "mozilla/firefox/pull/42",
        ),
        ("https://example.com/not/github", None),
        ("", None),
        (None, None),
    ],
)
def test_github_id(url, expected):
    assert github_id(url) == expected


# ---------------------------------------------------------------------------
# bugzilla_id
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://bugzilla.example.net/show_bug.cgi?id=1234567", "1234567"),
        ("https://example.com/not/bugzilla", None),
        ("", None),
        (None, None),
    ],
)
def test_bugzilla_id(url, expected):
    assert bugzilla_id(url) == expected


# ---------------------------------------------------------------------------
# ActionItem.tracker
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://jira.example.net/browse/IIM-10", "jira"),
        ("https://bugzilla.example.net/show_bug.cgi?id=999", "bugzilla"),
        ("https://github.com/mozilla/firefox/issues/5", "github"),
        ("https://github.com/mozilla/firefox/pull/5", "github"),
        ("https://example.com/some/task", None),
        (None, None),
    ],
)
def test_action_item_tracker(url, expected):
    item = ActionItem(url=url)
    assert item.tracker() == expected


# ---------------------------------------------------------------------------
# ActionItem.is_changed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "old_data, new_data, expected",
    [
        # Either side is None → always changed
        (None, ActionItem(url="https://example.com/", title="t", status="open"), True),
        (ActionItem(url="https://example.com/", title="t", status="open"), None, True),
        (None, None, True),
        # URL differs → changed
        (
            ActionItem(url="https://example.com/1", title="t", status="open"),
            ActionItem(url="https://example.com/2", title="t", status="open"),
            True,
        ),
        # Jira URL: title/status differences are ignored
        (
            ActionItem(
                url="https://jira.example.net/browse/IIM-1", title="old", status="open"
            ),
            ActionItem(
                url="https://jira.example.net/browse/IIM-1",
                title="new",
                status="closed",
            ),
            False,
        ),
        # Non-Jira: title differs → changed
        (
            ActionItem(url="https://example.com/task", title="old", status="open"),
            ActionItem(url="https://example.com/task", title="new", status="open"),
            True,
        ),
        # Non-Jira: status differs → changed
        (
            ActionItem(url="https://example.com/task", title="t", status="open"),
            ActionItem(url="https://example.com/task", title="t", status="closed"),
            True,
        ),
        # Identical → not changed
        (
            ActionItem(url="https://example.com/task", title="t", status="open"),
            ActionItem(url="https://example.com/task", title="t", status="open"),
            False,
        ),
    ],
)
def test_is_changed(old_data, new_data, expected):
    assert ActionItem.is_changed(old_data, new_data) is expected


# ---------------------------------------------------------------------------
# IncidentReport.tracked_action_items
# ---------------------------------------------------------------------------


def test_tracked_action_items_filters_no_url():
    report = IncidentReport(
        action_items=[
            ActionItem(url="https://example.com/task", title="has url"),
            ActionItem(title="no url"),
            ActionItem(),
        ]
    )
    tracked = report.tracked_action_items
    assert len(tracked) == 1
    assert tracked[0].url == "https://example.com/task"


def test_tracked_action_items_empty():
    report = IncidentReport(action_items=[])
    assert report.tracked_action_items == []


def test_tracked_action_items_none():
    report = IncidentReport()
    assert report.tracked_action_items == []


# ---------------------------------------------------------------------------
# ActionItem.essence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "item, expected",
    [
        (
            ActionItem(url="https://jira.example.net/browse/IIM-42"),
            "IIM-42",
        ),
        (
            ActionItem(
                url="https://bugzilla.example.net/show_bug.cgi?id=123",
                status="open",
                title="Fix the thing",
            ),
            "action: [open] https://bugzilla.example.net/show_bug.cgi?id=123 Fix the thing",
        ),
        (
            ActionItem(
                url="https://github.com/mozilla/firefox/issues/5",
                status="closed",
                title="PR merged",
            ),
            "action: [closed] https://github.com/mozilla/firefox/issues/5 PR merged",
        ),
    ],
)
def test_essence(item, expected):
    assert item.essence() == expected


# ---------------------------------------------------------------------------
# ActionItem.from_essence
# ---------------------------------------------------------------------------


def test_from_essence_valid():
    url = "https://bugzilla.example.net/show_bug.cgi?id=123"
    title = f"action: [open] {url} Fix the thing"
    item = ActionItem.from_essence(url=url, title=title)
    assert item.url == url
    assert item.status == "open"
    assert item.title == "Fix the thing"
    assert item.jira_id is None


def test_from_essence_with_jira_id():
    url = "https://github.com/mozilla/firefox/issues/5"
    title = f"action: [closed] {url} PR merged"
    item = ActionItem.from_essence(url=url, title=title, jira_id="link-99")
    assert item.status == "closed"
    assert item.jira_id == "link-99"


def test_from_essence_no_match():
    item = ActionItem.from_essence(url="https://example.com/", title="not an essence")
    assert item is None


def test_from_essence_roundtrip():
    original = ActionItem(
        url="https://bugzilla.example.net/show_bug.cgi?id=42",
        status="open",
        title="Fix the thing",
    )
    reconstructed = ActionItem.from_essence(url=original.url, title=original.essence())
    assert reconstructed.url == original.url
    assert reconstructed.status == original.status
    assert reconstructed.title == original.title


# ---------------------------------------------------------------------------
# IncidentReport.is_completed
# ---------------------------------------------------------------------------


def test_is_completed_with_completed_label():
    report = IncidentReport(labels=["completed"])
    assert report.is_completed is True


def test_is_completed_with_multiple_labels_including_completed():
    report = IncidentReport(labels=["foo", "completed", "bar"])
    assert report.is_completed is True


def test_is_completed_without_completed_label():
    report = IncidentReport(labels=["foo", "bar"])
    assert report.is_completed is False


def test_is_completed_with_empty_labels():
    report = IncidentReport()
    assert report.is_completed is False
