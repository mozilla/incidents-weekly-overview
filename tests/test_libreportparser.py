# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from pathlib import Path

import marko
import pytest

from iim.libreport import IncidentReport
from iim.libreportparser import (
    NoJiraKeyError,
    NoJiraURLError,
    extract_jira_key,
    extract_jira_url,
    extract_timestamp,
    is_table,
    metadata_table_to_report,
    parse_markdown,
)


REPORTS_DIR = Path(__file__).parent / "data"


# ---------------------------------------------------------------------------
# extract_jira_url
# ---------------------------------------------------------------------------


def test_extract_jira_url_markdown_link():
    assert (
        extract_jira_url("[IIM-131](https://jira.example.com/browse/IIM-131)")
        == "https://jira.example.com/browse/IIM-131"
    )


def test_extract_jira_url_plain_url():
    assert (
        extract_jira_url("https://mozilla-hub.atlassian.net/browse/IIM-95")
        == "https://mozilla-hub.atlassian.net/browse/IIM-95"
    )


def test_extract_jira_url_no_url():
    with pytest.raises(NoJiraURLError):
        extract_jira_url("no jira url here")


# ---------------------------------------------------------------------------
# extract_jira_key
# ---------------------------------------------------------------------------


def test_extract_jira_key_from_url():
    assert extract_jira_key("https://jira.example.com/browse/IIM-131") == "IIM-131"


def test_extract_jira_key_no_key():
    with pytest.raises(NoJiraKeyError):
        extract_jira_key("https://example.com/no/key/here")


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
    assert data.key == "IIM-131"
    assert data.jira_url == "https://example.com/browse/IIM-131"
    assert data.severity == "S2"
    assert data.detection_method == "Manual"
    assert data.status == "Mitigated"
    assert data.impact_start is not None
    assert data.mitigated is not None


def test_parse_markdown_bravoservice():
    bravoservice_md = (REPORTS_DIR / "incident_bravoservice_v20250520.md").read_text()
    data = parse_markdown(bravoservice_md)
    assert data.key == "IIM-133"
    assert data.jira_url == "https://example.com/browse/IIM-133"
    assert data.severity == "S3"
    assert data.detection_method == "Automation"
    assert data.status == "Mitigated"


# ---------------------------------------------------------------------------
# metadata_table_to_report
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


def test_metadata_table_to_report_happy():
    report = IncidentReport()
    ast = marko.Markdown().parse(SAMPLE_TABLE)
    table_token = next(t for t in ast.children if is_table(t))
    report = metadata_table_to_report(report, table_token)
    assert report.key == "IIM-99"
    assert report.jira_url == "https://jira.example.com/browse/IIM-99"
    assert report.severity == "S2"
    assert report.status == "Mitigated"
    assert report.detection_method == "Manual"
    assert report.impact_start == "2026-01-01 10:00"
    assert report.mitigated == "2026-01-01 11:00"
    assert report.resolved == "2026-01-01 12:00"


SAMPLE_TABLE_2 = r"""\

| Incident Severity | *Consider the business impact as you set this Severity. Refer to [this guide](https://confluence.example.net/wiki/spaces/MIR/pages/20512894/Incident+Severity+Levels). If the priority of your incident changes during its lifecycle, please capture this in the Timeline section and one of the written sections. Include rationale for why you assigned this severity level.* S2 \- High |
| :---- | :---- |
| **Incident Title** | Some Incident |
| **Jira Ticket/Bug Number** | [https://jira.example.net/browse/BFF-122](https://jira.example.net/browse/BFF-122) [IIM-1000](https://jira.example.net/browse/IIM-1000)  |
| **Time of first Impact** | *This is the time the impact first started.* 2026-03-02 |
| **Time Detected** | *Our automation detected a deviation from normal service health.* 2026-03-02 07:50  |
| **Time Alerted** | *Yardstick\<\>Slack alert integration sent its first alert* 2026-03-02 07:50  |
| **Time Acknowledged** | *The first page was ACK'd, or in some other way a responding engineer acknowledged the incident.* 2026-03-03 18:18 |
| **Time Responded/Engaged** | *First moment the problem was being engaged (i.e. reading errors, graphs, etc to begin understanding what was wrong / why the alert even triggered)* 2026-03-03 18:18 |
| **Time Mitigated (Repaired)** | *SES sending privileges were restored and emails beginning to be reprocessed.* 2026-03-05 00:13 |
| **Time Resolved** | *All unprocessed emails were sent* 2026-03-06 01:02 |
| **Issue detected via** | **Automated Alert** |
| **Video Call Link** |  |
| **Slack Channel** | #incident-20260302-some-incident |
| **Current Status** | **Resolved** |
"""


def test_metadata_table_multiple_issues():
    report = IncidentReport()
    ast = marko.Markdown().parse(SAMPLE_TABLE_2)
    table_token = next(t for t in ast.children if is_table(t))
    report = metadata_table_to_report(report, table_token)
    assert report.key == "IIM-1000"
    assert report.jira_url == "https://jira.example.net/browse/IIM-1000"
    assert report.severity == "S2"
    assert report.status == "Resolved"
    assert report.detection_method == "Automation"
    assert report.impact_start == "2026-03-02 00:00"
    assert report.mitigated == "2026-03-05 00:13"
    assert report.resolved == "2026-03-06 01:02"
