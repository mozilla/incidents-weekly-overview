# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import arrow

from iim.iim_to_review import filter_incidents, render_report
from iim.libreport import IncidentReport


JIRA_URL = "https://jira.example.com"
REPORT_URL = "https://docs.google.com/document/d/abc123/edit"

# Timestamps clearly inside and outside the 3-month window
IN_WINDOW = arrow.now().shift(months=-1).format("YYYY-MM-DD HH:mm")
OUT_OF_WINDOW = arrow.now().shift(months=-4).format("YYYY-MM-DD HH:mm")


def _resolved_incident(**kwargs):
    defaults = dict(
        key="IIM-42",
        summary="Everything is on fire",
        status="Resolved",
        severity="S1",
        resolved=IN_WINDOW,
        declare_date="2026-01-22",
        jira_url=f"{JIRA_URL}/browse/IIM-42",
        report_url=REPORT_URL,
        labels=[],
    )
    defaults.update(kwargs)
    return IncidentReport(**defaults)


# ---------------------------------------------------------------------------
# filter_incidents
# ---------------------------------------------------------------------------


def test_filter_incidents_includes_resolved_incomplete():
    incident = _resolved_incident()
    resolved_in_window, to_review = filter_incidents([incident])
    assert incident in resolved_in_window
    assert incident in to_review


def test_filter_incidents_excludes_completed_from_to_review():
    incident = _resolved_incident(labels=["completed"])
    resolved_in_window, to_review = filter_incidents([incident])
    assert incident in resolved_in_window
    assert incident not in to_review


def test_filter_incidents_excludes_outside_window():
    incident = _resolved_incident(resolved=OUT_OF_WINDOW)
    resolved_in_window, to_review = filter_incidents([incident])
    assert incident not in resolved_in_window
    assert incident not in to_review


def test_filter_incidents_excludes_non_resolved_status():
    incident = _resolved_incident(status="In Progress", resolved=None)
    resolved_in_window, to_review = filter_incidents([incident])
    assert incident not in resolved_in_window
    assert incident not in to_review


def test_filter_incidents_excludes_missing_resolved_timestamp():
    incident = _resolved_incident(resolved=None)
    resolved_in_window, to_review = filter_incidents([incident])
    assert incident not in resolved_in_window
    assert incident not in to_review


def test_filter_incidents_counts():
    complete = _resolved_incident(key="IIM-1", labels=["completed"])
    incomplete = _resolved_incident(key="IIM-2")
    old = _resolved_incident(key="IIM-3", resolved=OUT_OF_WINDOW)
    resolved_in_window, to_review = filter_incidents([complete, incomplete, old])
    assert len(resolved_in_window) == 2
    assert len(to_review) == 1
    assert to_review[0].key == "IIM-2"


# ---------------------------------------------------------------------------
# render_report
# ---------------------------------------------------------------------------


def test_render_report_all_completed():
    output = render_report(resolved_in_window=[_resolved_incident()], to_review=[])
    assert "# Incidents to Review" in output
    assert (
        "All 1 resolved incidents in the last 3 months have been completed." in output
    )


def test_render_report_header_counts():
    complete = _resolved_incident(key="IIM-1", labels=["completed"])
    incomplete = _resolved_incident(key="IIM-2")
    _, to_review = filter_incidents([complete, incomplete])
    output = render_report([complete, incomplete], to_review)
    assert "1 of 2 resolved incidents in the last 3 months are incomplete." in output


def test_render_report_incident_heading():
    incident = _resolved_incident()
    output = render_report([incident], [incident])
    assert "## IIM-42: Everything is on fire\n" in output


def test_render_report_severity():
    incident = _resolved_incident(severity="S2")
    output = render_report([incident], [incident])
    assert "- **Severity:** S2" in output


def test_render_report_severity_none():
    incident = _resolved_incident(severity=None)
    output = render_report([incident], [incident])
    assert "- **Severity:** unknown" in output


def test_render_report_resolved_timestamp():
    incident = _resolved_incident()
    output = render_report([incident], [incident])
    assert f"- **Resolved:** {IN_WINDOW} (" in output
    assert "ago)" in output


def test_render_report_jira_link():
    incident = _resolved_incident()
    output = render_report([incident], [incident])
    assert f"- **Jira:** [IIM-42]({JIRA_URL}/browse/IIM-42)" in output


def test_render_report_report_link():
    incident = _resolved_incident()
    output = render_report([incident], [incident])
    assert f"- **Report:** [incident report]({REPORT_URL})" in output


def test_render_report_no_doc_sentinel():
    incident = _resolved_incident(report_url="no doc")
    output = render_report([incident], [incident])
    assert "- **Report:** no report" in output


def test_render_report_no_doc_none():
    incident = _resolved_incident(report_url=None)
    output = render_report([incident], [incident])
    assert "- **Report:** no report" in output


def test_render_report_sort_order_descending():
    older = _resolved_incident(
        key="IIM-1",
        resolved=arrow.now().shift(months=-2).format("YYYY-MM-DD HH:mm"),
    )
    newer = _resolved_incident(
        key="IIM-2",
        resolved=arrow.now().shift(days=-7).format("YYYY-MM-DD HH:mm"),
    )
    output = render_report([older, newer], [older, newer])
    assert output.index("IIM-2") < output.index("IIM-1")
