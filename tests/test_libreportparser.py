# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from pathlib import Path

import marko
import pytest

from iim.libreport import IncidentReport
from iim.libreportparser import (
    NoJiraIIMKeyError,
    NoJiraIIMURLError,
    ReportParser20250520,
    ReportParser20260312,
    ReportParserPre20250520,
    extract_jira_key,
    extract_jira_iim_url,
    extract_timestamp,
    get_text,
    is_table,
    normalize_entities,
    parse_markdown,
)


REPORTS_DIR = Path(__file__).parent / "data"


# ---------------------------------------------------------------------------
# extract_jira_iim_url
# ---------------------------------------------------------------------------


def test_extract_jira_iim_url_markdown_link():
    assert (
        extract_jira_iim_url("[IIM-131](https://jira.example.com/browse/IIM-131)")
        == "https://jira.example.com/browse/IIM-131"
    )


def test_extract_jira_iim_url_plain_url():
    assert (
        extract_jira_iim_url("https://mozilla-hub.atlassian.net/browse/IIM-95")
        == "https://mozilla-hub.atlassian.net/browse/IIM-95"
    )


def test_extract_jira_iim_url_no_url():
    with pytest.raises(NoJiraIIMURLError):
        extract_jira_iim_url("no jira url here")


# ---------------------------------------------------------------------------
# extract_jira_key
# ---------------------------------------------------------------------------


def test_extract_jira_key_from_url():
    assert extract_jira_key("https://jira.example.com/browse/IIM-131") == "IIM-131"


def test_extract_jira_key_no_key():
    with pytest.raises(NoJiraIIMKeyError):
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
        # ISO 8601 format with T separator and Z suffix
        ("2025-01-27T16:00:00Z UTC", "2025-01-27 16:00"),
        ("2025-01-27T16:03:00Z", "2025-01-27 16:03"),
        # no dates -- return None
        ("non-date", None),
        (None, None),
    ],
)
def test_extract_timestamp(text, expected):
    assert extract_timestamp(text) == expected


# ---------------------------------------------------------------------------
# get_text
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "md, keep_links, expected",
    [
        # plain text — unaffected by keep_links
        ("just text", True, "just text"),
        ("just text", False, "just text"),
        # link with keep_links=True preserves markdown link syntax
        (
            "abc [link title](https://example.com/)",
            True,
            "abc [link title](https://example.com/)",
        ),
        # link with keep_links=False strips URL, keeps visible text
        ("abc [link title](https://example.com/)", False, "abc link title"),
        # link with no visible text falls back to "Link"
        ("[](https://example.com/)", True, "[Link](https://example.com/)"),
        ("[](https://example.com/)", False, "Link"),
    ],
)
def test_get_text(md, keep_links, expected):
    ast = marko.Markdown().parse(md)
    # parse_markdown wraps content in a Document > Paragraph
    paragraph = ast.children[0]
    result = get_text(paragraph, keep_links=keep_links)
    assert result == expected


# ---------------------------------------------------------------------------
# normalize_entities
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("fenix", "fenix"),
        ("  fxa,  fenix", "fenix, fxa"),
        ("FXA, Fenix", "fenix, fxa"),
        ("testreport, incidents", "incidents, testreport"),
    ],
)
def test_normalize_entities(value, expected):
    assert normalize_entities(value) == expected


# ---------------------------------------------------------------------------
# parse_markdown - ReportParser20250520
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
    assert data.action_items == []


def test_parse_markdown_bravoservice():
    bravoservice_md = (REPORTS_DIR / "incident_bravoservice_v20250520.md").read_text()
    data = parse_markdown(bravoservice_md)
    assert data.key == "IIM-133"
    assert data.jira_url == "https://example.com/browse/IIM-133"
    assert data.severity == "S3"
    assert data.detection_method == "Automation"
    assert data.status == "Mitigated"
    assert len(data.action_items) == 2
    assert data.action_items[0].url == "https://example.com/browse/PUSH-630"
    assert data.action_items[1].url == "https://example.com/browse/INFRASEC-2653"


# ---------------------------------------------------------------------------
# ReportParser20250520.action_items_table_to_report
# ---------------------------------------------------------------------------


def test_action_items_table_mailto_dropped():
    """Action items whose ticket cell contains only a mailto URL are dropped."""
    md = """\
# Incident: *test*

| **Jira Ticket/Bug Number** | [IIM-1](https://example.com/browse/IIM-1) |
| :---- | :---- |
| **Current Status** | Resolved |
| **Issue detected via** | Manual/Human |

# Postmortem Action Items

| Jira Ticket + Status | Ticket Title |
| :---- | :---- |
| [[WORK-1](https://example.com/browse/WORK-1)] | Keep this one |
| [Bianca](mailto:bianca@example.net) | Drop this one |
"""
    data = parse_markdown(md)
    assert len(data.action_items) == 1
    assert data.action_items[0].url == "https://example.com/browse/WORK-1"


# ---------------------------------------------------------------------------
# ReportParser20250520.metadata_table_to_report
# ---------------------------------------------------------------------------


SAMPLE_TABLE_20250520 = """\
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
    parser = ReportParser20250520()
    ast = marko.Markdown().parse(SAMPLE_TABLE_20250520)
    table_token = next(t for t in ast.children if is_table(t))
    report = parser.metadata_table_to_report(report, table_token)
    assert report.key == "IIM-99"
    assert report.jira_url == "https://jira.example.com/browse/IIM-99"
    assert report.severity == "S2"
    assert report.status == "Mitigated"
    assert report.detection_method == "Manual"
    assert report.impact_start == "2026-01-01 10:00"
    assert report.mitigated == "2026-01-01 11:00"
    assert report.resolved == "2026-01-01 12:00"


SAMPLE_TABLE_2_20250520 = r"""\

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
    parser = ReportParser20250520()
    ast = marko.Markdown().parse(SAMPLE_TABLE_2_20250520)
    table_token = next(t for t in ast.children if is_table(t))
    report = parser.metadata_table_to_report(report, table_token)
    assert report.key == "IIM-1000"
    assert report.jira_url == "https://jira.example.net/browse/IIM-1000"
    assert report.severity == "S2"
    assert report.status == "Resolved"
    assert report.detection_method == "Automation"
    assert report.impact_start == "2026-03-02 00:00"
    assert report.mitigated == "2026-03-05 00:13"
    assert report.resolved == "2026-03-06 01:02"


# ---------------------------------------------------------------------------
# ReportParser20260312.metadata_table_to_report
# ---------------------------------------------------------------------------


SAMPLE_TABLE_20260312 = """\
| Incident Severity *rationale* | S2 \\- High |
| :---- | :---- |
| **Current Status** | **Resolved** |
| **Jira Ticket/Bug Number** | [IIM-200](https://jira.example.com/browse/IIM-200) |
| **Time declared** *description* YYYY-MM-DD hh:mm | 2026-03-12 01:00 |
| **Time of first Impact** *description* YYYY-MM-DD hh:mm | 2026-03-12 02:00 |
| **Time Alerted** *description* YYYY-MM-DD hh:mm | 2026-03-12 03:00 |
| **Time Acknowledged** *description* YYYY-MM-DD hh:mm | 2026-03-12 04:00 |
| **Time Responded/Engaged** *description* YYYY-MM-DD hh:mm | 2026-03-12 05:00 |
| **Time Mitigated (Repaired)** *description* YYYY-MM-DD hh:mm | 2026-03-12 06:00 |
| **Time Resolved** *description* YYYY-MM-DD hh:mm | 2026-03-12 07:00 |
| **Detection method** | **Automated Alert** |
| **Impacted entities** *description* | testreport, incidents |
"""


def test_metadata_table_to_report_v20260312():
    report = IncidentReport()
    parser = ReportParser20260312()
    ast = marko.Markdown().parse(SAMPLE_TABLE_20260312)
    table_token = next(t for t in ast.children if is_table(t))
    report = parser.metadata_table_to_report(report, table_token)
    assert report.key == "IIM-200"
    assert report.jira_url == "https://jira.example.com/browse/IIM-200"
    assert report.severity == "S2"
    assert report.status == "Resolved"
    assert report.detection_method == "Automation"
    assert report.declared == "2026-03-12 01:00"
    assert report.impact_start == "2026-03-12 02:00"
    assert report.alerted == "2026-03-12 03:00"
    assert report.acknowledged == "2026-03-12 04:00"
    assert report.responded == "2026-03-12 05:00"
    assert report.mitigated == "2026-03-12 06:00"
    assert report.resolved == "2026-03-12 07:00"
    assert report.entities == "incidents, testreport"


def test_metadata_table_to_report_v20260312_manual_detection():
    report = IncidentReport()
    parser = ReportParser20260312()
    table_md = """\
| **Jira Ticket/Bug Number** | [IIM-201](https://jira.example.com/browse/IIM-201) |
| :---- | :---- |
| **Detection method** | **Manual/Human** |
| **Current Status** | Resolved |
"""
    ast = marko.Markdown().parse(table_md)
    table_token = next(t for t in ast.children if is_table(t))
    report = parser.metadata_table_to_report(report, table_token)
    assert report.detection_method == "Manual"


# ---------------------------------------------------------------------------
# parse_markdown - ReportParser20260312
# ---------------------------------------------------------------------------


def test_parse_markdown_v20260312_no_jira_url():
    """The test document has an empty Jira ticket field."""
    md = (REPORTS_DIR / "2026_03_13_test_report_v20260312.md").read_text()
    with pytest.raises(NoJiraIIMURLError):
        parse_markdown(md)


def test_parse_markdown_v20260312_summary():
    """Summary is extracted from the # Incident: header, not a table row."""
    report = IncidentReport()
    parser = ReportParser20260312()
    md = (REPORTS_DIR / "2026_03_13_test_report_v20260312.md").read_text()
    try:
        parser.parse_markdown(report, md)
    except NoJiraIIMURLError:
        pass
    assert report.summary == "Test report affecting 0 users for 0 minutes"


def test_parse_markdown_v20250520_sets_template_version():
    md = (REPORTS_DIR / "incident_service_alpha_v20250520.md").read_text()
    report = parse_markdown(md)
    assert report.template_version == "2025.05.20"


def test_parse_markdown_v20260312_sets_template_version():
    report = IncidentReport()
    parser = ReportParser20260312()
    md = (REPORTS_DIR / "2026_03_13_test_report_v20260312.md").read_text()
    try:
        parser.parse_markdown(report, md)
    except NoJiraIIMURLError:
        pass
    assert report.template_version == "2026.03.12"


def test_parse_markdown_selects_v20260312_parser():
    """parse_markdown selects ReportParser20260312 when template version is present."""
    # Build a minimal v20260312 document with a real IIM URL
    md = """\
# Incident: Parser selection test

Template version 2026.03.12

| **Jira Ticket/Bug Number** | [IIM-999](https://jira.example.com/browse/IIM-999) |
| :---- | :---- |
| **Current Status** | Resolved |
| **Detection method** | **Automated Alert** |

# Postmortem Action Items

| Jira Ticket + Status | Ticket Title |
| :---- | :---- |
"""
    report = parse_markdown(md)
    assert report.key == "IIM-999"
    assert report.status == "Resolved"
    assert report.detection_method == "Automation"
    assert report.template_version == "2026.03.12"


# ---------------------------------------------------------------------------
# ReportParserPre20250520.metadata_list_to_report
# ---------------------------------------------------------------------------


SAMPLE_LIST_PRE20250520 = """\
* **Incident Severity**: S2 \\- High
* **Incident Jira Ticket**: [SREIM-17](https://example.net/browse/SREIM-17) [IIM-50](https://example.net/browse/IIM-50)
* **Time of first Impact:** 2025-01-27T16:00:00Z UTC
* **Time Alerted**: 2025-01-27T16:05:00Z UTC
* **Time Acknowledge**: 2025-01-27T16:05:00Z UTC
* **Time Responded/Engaged**: 2025-01-27T16:03:00Z UTC
* **Time Mitigated (Repaired)**: 2025-01-27T16:19:00Z UTC
* **Time Resolved**: 2025-01-27T16:19:00Z UTC
* **Current Status**: \\[Resolved\\]
"""


def test_metadata_list_to_report():
    report = IncidentReport()
    parser = ReportParserPre20250520()
    ast = marko.Markdown().parse(SAMPLE_LIST_PRE20250520)
    list_token = next(t for t in ast.children if isinstance(t, marko.block.List))
    parser.metadata_list_to_report(report, list_token)
    assert report.key == "IIM-50"
    assert report.jira_url == "https://example.net/browse/IIM-50"
    assert report.severity == "S2"
    assert report.status == "Resolved"
    assert report.impact_start == "2025-01-27 16:00"
    assert report.alerted == "2025-01-27 16:05"
    assert report.acknowledged == "2025-01-27 16:05"
    assert report.responded == "2025-01-27 16:03"
    assert report.mitigated == "2025-01-27 16:19"
    assert report.resolved == "2025-01-27 16:19"


# ---------------------------------------------------------------------------
# ReportParserPre20250520.action_items_list_to_report
# ---------------------------------------------------------------------------


SAMPLE_ACTION_ITEMS_PRE20250520 = """\
- [ ] \\[[WORK-1](https://example.net/browse/WORK-1)\\] Do the open thing.
- [x] ~~\\[[WORK-2](https://example.net/browse/WORK-2)\\] Done thing.~~
- [ ] \\[Jira TBC\\] No ticket yet.
"""


def test_action_items_list_to_report():
    report = IncidentReport()
    parser = ReportParserPre20250520()
    ast = marko.Markdown().parse(SAMPLE_ACTION_ITEMS_PRE20250520)
    list_token = next(t for t in ast.children if isinstance(t, marko.block.List))
    parser.action_items_list_to_report(report, list_token)
    assert len(report.action_items) == 3

    assert report.action_items[0].url == "https://example.net/browse/WORK-1"
    assert report.action_items[0].status == "OPEN"
    assert report.action_items[0].title == "Do the open thing."

    assert report.action_items[1].url == "https://example.net/browse/WORK-2"
    assert report.action_items[1].status == "DONE"
    assert report.action_items[1].title == "Done thing."

    assert report.action_items[2].url is None
    assert report.action_items[2].status == "OPEN"
    assert report.action_items[2].title == "No ticket yet."


# ---------------------------------------------------------------------------
# parse_markdown - ReportParserPre20250520
# ---------------------------------------------------------------------------


def test_parse_markdown_deltaservice():
    """Full document parse of a pre-20250520 bullet-list-format incident report."""
    md = (REPORTS_DIR / "incident_deltaservice_pre_20250520.md").read_text()
    data = parse_markdown(md)
    assert data.key == "IIM-17"
    assert data.jira_url == "https://example.net/browse/IIM-17"
    assert data.summary == "delta.example.org returning 4xx\u2019s"
    assert data.severity == "S2"
    assert data.status == "Resolved"
    assert data.template_version == "pre-2025.05.20"
    assert data.impact_start == "2025-01-27 16:00"
    assert data.alerted == "2025-01-27 16:05"
    assert data.acknowledged == "2025-01-27 16:05"
    assert data.responded == "2025-01-27 16:03"
    assert data.mitigated == "2025-01-27 16:19"
    assert data.resolved == "2025-01-27 16:19"


def test_parse_markdown_deltaservice_action_items():
    """Action items from pre-20250520 format: correct count, URLs, and statuses."""
    md = (REPORTS_DIR / "incident_deltaservice_pre_20250520.md").read_text()
    data = parse_markdown(md)
    assert data.action_items is not None
    assert len(data.action_items) == 7

    # First two items have the same Jira ticket
    assert data.action_items[0].url == "https://example.net/browse/SE-4263"
    assert data.action_items[0].status == "OPEN"
    assert data.action_items[1].url == "https://example.net/browse/SE-4263"
    assert data.action_items[1].status == "OPEN"

    # Third item is completed (strikethrough / [x])
    assert data.action_items[2].url == "https://example.net/browse/OPST-1874"
    assert data.action_items[2].status == "DONE"

    # Remaining items have no Jira ticket yet
    for item in data.action_items[3:]:
        assert item.url is None
        assert item.status == "OPEN"


def test_parse_markdown_symbols():
    """Full document parse of symbols-style pre-20250520 report."""
    md = (REPORTS_DIR / "incident_symbols_pre20250520.md").read_text()
    data = parse_markdown(md)
    assert data.key == "IIM-17"
    assert data.jira_url == "https://example.net/browse/IIM-17"
    assert data.summary == "symbols outage with spiking load balancer 502s"
    assert data.severity == "S4"
    assert data.status == "Resolved"
    assert data.impact_start == "2025-02-21 16:41"
    assert data.mitigated == "2025-02-21 18:15"


def test_parse_markdown_symbols_action_items():
    """Action items from symbols-style report: trailing ticket ref stripped."""
    md = (REPORTS_DIR / "incident_symbols_pre20250520.md").read_text()
    data = parse_markdown(md)
    assert data.action_items is not None
    assert len(data.action_items) == 3
    assert data.action_items[0].url == "https://example.net/browse/OBS-508"
    assert data.action_items[0].status == "OPEN"
    assert data.action_items[0].title == (
        "Come up with a process to iterate on Helm chart changes in stage that does not"
        " involve locally running Helm. This will make the process less error-prone and"
        " more auditable. It's probably enough to add a parameter to select a different"
        " webservices-infra branch in our manual deployment playbooks."
    )
    assert data.action_items[1].url == "https://example.net/browse/OBS-507"
    assert data.action_items[2].url == "https://example.net/browse/OBS-509"


def test_parse_markdown_selects_pre20250520_parser():
    """parse_markdown routes to ReportParserPre20250520 for bullet-list format."""
    md = """\
# Incident: *parser selection test*

* **Incident [Severity](https://example.net/wiki/severity)**: S2 \\- High
* **Incident Jira Ticket**: [IIM-42](https://example.net/browse/IIM-42)
* **Time of first Impact:** 2025-06-01T10:00:00Z UTC
* **Time Mitigated (Repaired)**: 2025-06-01T10:30:00Z UTC
* **Time Resolved**: 2025-06-01T10:30:00Z UTC
* **Current Status**: \\[Resolved\\]

# Postmortem Action Items

- [ ] \\[Jira TBC\\] Fix the thing.
"""
    report = parse_markdown(md)
    assert report.key == "IIM-42"
    assert report.severity == "S2"
    assert report.status == "Resolved"
    assert report.template_version == "pre-2025.05.20"
    assert report.impact_start == "2025-06-01 10:00"
    assert report.mitigated == "2025-06-01 10:30"
    assert len(report.action_items) == 1
    assert report.action_items[0].title == "Fix the thing."
    assert report.action_items[0].status == "OPEN"
