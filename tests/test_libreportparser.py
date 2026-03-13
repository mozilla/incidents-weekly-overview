# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from pathlib import Path

import pytest

from iim.libreportparser import (
    extract_jira_issue,
    extract_timestamp,
    metadata_table_to_dict,
    parse_markdown,
)


REPORTS_DIR = Path(__file__).parent / "data"


# ---------------------------------------------------------------------------
# extract_jira_issue
# ---------------------------------------------------------------------------


def test_extract_jira_issue_link():
    assert (
        extract_jira_issue("[IIM-131](https://jira.example.com/browse/IIM-131)")
        == "IIM-131"
    )


def test_extract_jira_issue_bare_key():
    assert extract_jira_issue("IIM-42") == "IIM-42"


def test_extract_jira_issue_no_key():
    with pytest.raises(Exception):
        extract_jira_issue("no jira issue here")


# ---------------------------------------------------------------------------
# extract_timestamp
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, expected",
    [
        # date and time
        ("2026-02-21 08:57", "2026-02-21 08:57"),
        (
            " bunch of text 2026-02-21 08:57 bunch of text",
            "2026-02-21 08:57",
        ),
        # just the date -- converts to midnight
        ("2026-02-21", "2026-02-21 00:00"),
        # no dates -- return None
        ("non-date", None),
        (None, None),
    ],
)
def test_extract_timestamp(text, expected):
    assert extract_timestamp(text) == expected


# ---------------------------------------------------------------------------
# parse_markdown
# ---------------------------------------------------------------------------


def test_parse_markdown_service_alpha():
    service_alpha_md = (REPORTS_DIR / "incident_service_alpha_v20250520.md").read_text()
    data = parse_markdown(service_alpha_md)
    assert data["key"] == "IIM-131"
    assert data["severity"] == {"value": "S2"}
    assert data["detection method"] == {"value": "Manual"}
    assert data["status"] == "Mitigated"
    assert data["impact start"] is not None
    assert data["detected"] is not None
    assert data["mitigated"] is not None


def test_parse_markdown_bravoservice():
    bravoservice_md = (REPORTS_DIR / "incident_bravoservice_v20250520.md").read_text()
    data = parse_markdown(bravoservice_md)
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
    assert data["impact start"] == "2026-01-01 10:00"
    assert data["mitigated"] == "2026-01-01 11:00"
    assert data["resolved"] == "2026-01-01 12:00"
