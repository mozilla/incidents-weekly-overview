# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from datetime import timedelta

import arrow
import click
import pytest

from iim.iim_data import filter_incidents, parse_period
from iim.libreport import IncidentReport


def _ts_days_ago(n: int) -> str:
    """ISO timestamp string for N days ago."""
    return arrow.now().shift(days=-n).isoformat()


def _make(
    key: str,
    status: str = "Resolved",
    resolved: str | None = None,
    report_modified: str | None = None,
) -> IncidentReport:
    return IncidentReport(
        key=key,
        status=status,
        resolved=resolved,
        report_modified=report_modified,
    )


@pytest.mark.parametrize(
    "value, kwargs",
    [
        ("1d", {"days": -1}),
        ("7d", {"days": -7}),
        ("0d", {"days": 0}),
        ("365d", {"days": -365}),
        ("1w", {"weeks": -1}),
        ("2w", {"weeks": -2}),
        ("1mo", {"months": -1}),
        ("6mo", {"months": -6}),
        ("12mo", {"months": -12}),
        ("1y", {"years": -1}),
        ("10y", {"years": -10}),
    ],
)
def test_parse_period_valid(value, kwargs):
    expected = arrow.now().shift(**kwargs)
    result = parse_period(value)
    # parse_period and the test each call arrow.now(), so they're a few
    # microseconds apart — allow a generous tolerance.
    assert abs(result - expected) < timedelta(seconds=5)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "d",
        "7",
        "7days",
        "7m",  # ambiguous: minutes? months? — only "mo" is accepted
        "1.5d",
        "-7d",
        "+7d",
        " 7d",
        "7d ",
        "7D",
        "7MO",
        "abc",
        "7d7d",
    ],
)
def test_parse_period_invalid(value):
    with pytest.raises(click.BadParameter):
        parse_period(value)


def test_parse_period_calendar_aware_months():
    """Months use calendar math (not 30-day approximation)."""
    cal_expected = arrow.now().shift(months=-1)
    result = parse_period("1mo")
    assert abs(result - cal_expected) < timedelta(seconds=5)


def test_parse_period_calendar_aware_years():
    """Years use calendar math (handles leap years)."""
    expected = arrow.now().shift(years=-1)
    result = parse_period("1y")
    assert abs(result - expected) < timedelta(seconds=5)


# ---------------------------------------------------------------------------
# filter_incidents
# ---------------------------------------------------------------------------


def test_filter_incidents_no_show_returns_all():
    incidents = [_make("IIM-1"), _make("IIM-2", status="Open")]
    header, selected = filter_incidents(incidents, show=None, period=None)
    assert header == "All incidents (2)"
    assert selected == incidents


def test_filter_incidents_no_show_ignores_period():
    incidents = [_make("IIM-1")]
    # show=None doesn't call parse_period — even garbage is harmless
    header, selected = filter_incidents(incidents, show=None, period="garbage")
    assert selected == incidents


def test_filter_incidents_active_only_unresolved():
    incidents = [
        _make("IIM-1", status="Open"),
        _make("IIM-2", status="Resolved"),
        _make("IIM-3", status="In Progress"),
        _make("IIM-4", status="Mitigated"),
    ]
    header, selected = filter_incidents(incidents, show="active", period=None)
    assert "Active incidents" in header
    assert "(3)" in header
    assert [i.key for i in selected] == ["IIM-1", "IIM-3", "IIM-4"]


def test_filter_incidents_active_ignores_period():
    incidents = [_make("IIM-1", status="Open")]
    # active doesn't call parse_period — even garbage is harmless
    header, selected = filter_incidents(incidents, show="active", period="garbage")
    assert [i.key for i in selected] == ["IIM-1"]


def test_filter_incidents_resolved_default_period():
    incidents = [
        _make("IIM-1", status="Resolved", resolved=_ts_days_ago(3)),
        _make("IIM-2", status="Resolved", resolved=_ts_days_ago(30)),
        _make("IIM-3", status="Resolved", resolved=None),
        _make("IIM-4", status="Open", resolved=None),
    ]
    header, selected = filter_incidents(incidents, show="resolved", period=None)
    assert "7d" in header  # default
    assert [i.key for i in selected] == ["IIM-1"]


def test_filter_incidents_resolved_custom_period():
    incidents = [
        _make("IIM-1", status="Resolved", resolved=_ts_days_ago(3)),
        _make("IIM-2", status="Resolved", resolved=_ts_days_ago(20)),
        _make("IIM-3", status="Resolved", resolved=_ts_days_ago(40)),
    ]
    header, selected = filter_incidents(incidents, show="resolved", period="30d")
    assert "30d" in header
    assert [i.key for i in selected] == ["IIM-1", "IIM-2"]


def test_filter_incidents_working_includes_unresolved():
    # Unresolved incidents are in regardless of how stale the report is.
    incidents = [
        _make("IIM-1", status="Open", report_modified=_ts_days_ago(100)),
        _make("IIM-2", status="In Progress", report_modified=None),
    ]
    header, selected = filter_incidents(incidents, show="working", period="14d")
    assert [i.key for i in selected] == ["IIM-1", "IIM-2"]


def test_filter_incidents_working_includes_recently_modified_resolved():
    # Resolved-but-recently-touched is in.
    incidents = [
        _make("IIM-1", status="Resolved", report_modified=_ts_days_ago(3)),
        _make("IIM-2", status="Resolved", report_modified=_ts_days_ago(30)),
        _make("IIM-3", status="Resolved", report_modified=None),
    ]
    header, selected = filter_incidents(incidents, show="working", period="14d")
    assert "14d" in header
    assert [i.key for i in selected] == ["IIM-1"]


def test_filter_incidents_working_default_period():
    incidents = [_make("IIM-1", status="Open")]
    header, _ = filter_incidents(incidents, show="working", period=None)
    assert "14d" in header  # default


def test_filter_incidents_dormant():
    incidents = [
        # Unresolved + old report → in
        _make("IIM-1", status="Open", report_modified=_ts_days_ago(200)),
        # Unresolved + missing report_modified → in (treat as never touched)
        _make("IIM-2", status="Open", report_modified=None),
        # Unresolved + recently touched → out
        _make("IIM-3", status="Open", report_modified=_ts_days_ago(30)),
        # Resolved → out (regardless of touch time)
        _make("IIM-4", status="Resolved", report_modified=_ts_days_ago(200)),
    ]
    header, selected = filter_incidents(incidents, show="dormant", period="6mo")
    assert "6mo" in header
    assert sorted(i.key for i in selected) == ["IIM-1", "IIM-2"]


def test_filter_incidents_dormant_default_period():
    incidents = [_make("IIM-1", status="Open", report_modified=_ts_days_ago(365))]
    header, _ = filter_incidents(incidents, show="dormant", period=None)
    assert "6mo" in header  # default


def test_filter_incidents_invalid_period_propagates():
    with pytest.raises(click.BadParameter):
        filter_incidents([_make("IIM-1")], show="working", period="garbage")


def test_filter_incidents_empty_input():
    for show in (None, "working", "resolved", "active", "dormant"):
        header, selected = filter_incidents([], show=show, period=None)
        assert selected == []
        assert "(0)" in header
