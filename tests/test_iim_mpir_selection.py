# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import arrow

from iim.iim_mpir_selection import filter_incidents, format_incident_line, render_report
from iim.libreport import IncidentReport


JIRA_URL = "https://jira.example.net"
REPORT_URL = "https://docs.google.com/document/d/abc123/edit"

IN_WINDOW = arrow.now().shift(weeks=-1).format("YYYY-MM-DD")
OUT_OF_WINDOW = arrow.now().shift(weeks=-7).format("YYYY-MM-DD")


def _incident(**kwargs):
    defaults = dict(
        key="IIM-42",
        summary="Everything is on fire",
        status="Resolved",
        severity="S1",
        entities="relay",
        declare_date=IN_WINDOW,
        jira_url=f"{JIRA_URL}/browse/IIM-42",
        report_url=REPORT_URL,
        labels=[],
    )
    defaults.update(kwargs)
    return IncidentReport(**defaults)


# ---------------------------------------------------------------------------
# filter_incidents
# ---------------------------------------------------------------------------


def test_filter_incidents_includes_service_in_window():
    incident = _incident()
    result = filter_incidents([incident], weeks=5)
    assert incident in result


def test_filter_incidents_excludes_outside_window():
    incident = _incident(declare_date=OUT_OF_WINDOW)
    result = filter_incidents([incident], weeks=5)
    assert incident not in result


def test_filter_incidents_excludes_product_bucket():
    # "firefox" maps to product in the entity bucket JSON
    incident = _incident(entities="firefox")
    result = filter_incidents([incident], weeks=5)
    assert incident not in result


def test_filter_incidents_excludes_missing_declare_date():
    incident = _incident(declare_date=None)
    result = filter_incidents([incident], weeks=5)
    assert incident not in result


def test_filter_incidents_includes_boundary_date():
    boundary = arrow.now().shift(weeks=-5).format("YYYY-MM-DD")
    incident = _incident(declare_date=boundary)
    result = filter_incidents([incident], weeks=5)
    assert incident in result


def test_filter_incidents_unknown_entity_defaults_to_service():
    # Unknown entities default to "service" in entity_bucket
    incident = _incident(entities="totally-unknown-service-xyz")
    result = filter_incidents([incident], weeks=5)
    assert incident in result


# ---------------------------------------------------------------------------
# format_incident_line
# ---------------------------------------------------------------------------


def test_format_incident_line_basic():
    incident = _incident()
    line = format_incident_line(incident)
    assert line == (
        f"- [IIM-42]({JIRA_URL}/browse/IIM-42) "
        f"Resolved S1 relay [Everything is on fire]({REPORT_URL})"
    )


def test_format_incident_line_no_doc():
    incident = _incident(report_url="no doc")
    line = format_incident_line(incident)
    assert "Everything is on fire" in line
    assert "[Everything is on fire]" not in line


def test_format_incident_line_no_report_url():
    incident = _incident(report_url=None)
    line = format_incident_line(incident)
    assert "Everything is on fire" in line
    assert "[Everything is on fire]" not in line


def test_format_incident_line_severity_none():
    incident = _incident(severity=None)
    line = format_incident_line(incident)
    assert "unknown" in line


def test_format_incident_line_entities_none():
    incident = _incident(entities=None)
    line = format_incident_line(incident)
    assert "unknown" in line


# ---------------------------------------------------------------------------
# render_report
# ---------------------------------------------------------------------------


def test_render_report_no_incidents():
    output = render_report([], weeks=5, jira_url=JIRA_URL)
    assert "# Monthly Incident Meeting" in output
    assert "No service incidents declared in the last 5 weeks" in output


def test_render_report_header_count():
    incidents = [_incident(key="IIM-1"), _incident(key="IIM-2")]
    output = render_report(incidents, weeks=5, jira_url=JIRA_URL)
    assert "2 service incidents declared in the last 5 weeks" in output


def test_render_report_custom_weeks():
    output = render_report([], weeks=6, jira_url=JIRA_URL)
    assert "in the last 6 weeks" in output


def test_render_report_sort_by_severity():
    s2 = _incident(key="IIM-1", severity="S2", declare_date="2026-03-15")
    s1 = _incident(key="IIM-2", severity="S1", declare_date="2026-03-01")
    output = render_report([s2, s1], weeks=5, jira_url=JIRA_URL)
    assert output.index("IIM-2") < output.index("IIM-1")


def test_render_report_sort_date_within_severity():
    older = _incident(key="IIM-1", severity="S1", declare_date="2026-03-01")
    newer = _incident(key="IIM-2", severity="S1", declare_date="2026-03-15")
    output = render_report([older, newer], weeks=5, jira_url=JIRA_URL)
    assert output.index("IIM-2") < output.index("IIM-1")


def test_render_report_sort_unknown_severity_last():
    unknown = _incident(key="IIM-1", severity=None, declare_date="2026-03-15")
    s3 = _incident(key="IIM-2", severity="S3", declare_date="2026-03-01")
    output = render_report([unknown, s3], weeks=5, jira_url=JIRA_URL)
    assert output.index("IIM-2") < output.index("IIM-1")


def test_render_report_jira_link():
    incident = _incident()
    output = render_report([incident], weeks=5, jira_url=JIRA_URL)
    assert "[View in Jira](" in output
    assert "IIM-42" in output


def test_render_report_no_jira_link_when_empty():
    output = render_report([], weeks=5, jira_url=JIRA_URL)
    assert "View in Jira" not in output


def test_render_report_date_range_in_header():
    output = render_report([_incident()], weeks=5, jira_url=JIRA_URL)
    today = arrow.now().format("YYYY-MM-DD")
    start = arrow.now().shift(weeks=-5).format("YYYY-MM-DD")
    assert f"({start} to {today})" in output
