# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from datetime import timedelta

import pytest
from pytest import approx

from iim.iim_weekly_overview import friendly_date
from iim.libstats import (
    mean_timedelta,
    build_period_stats,
    compute_period_comparison,
    direction,
)
from iim.libreport import IncidentReport


# ---------------------------------------------------------------------------
# friendly_date
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "date_str,expected",
    [
        ("2026-03-20", "March 20, 2026"),
        ("2026-03-01", "March 1, 2026"),
        ("2026-01-15", "January 15, 2026"),
        ("2025-12-31", "December 31, 2025"),
    ],
)
def test_friendly_date(date_str, expected):
    assert friendly_date(date_str) == expected


def make_incident(**kwargs):
    defaults = dict(
        key="IIM-1",
        jira_url="https://jira.example.net/browse/IIM-1",
        severity="S3",
        status="Resolved",
        entities="auth",
        declare_date="2026-01-15",
        impact_start="2026-01-15 10:00",
        declared="2026-01-15 10:30",
        alerted="2026-01-15 10:20",
        mitigated="2026-01-15 11:00",
        resolved="2026-01-15 12:00",
    )
    defaults.update(kwargs)
    return IncidentReport(**defaults)


# ---------------------------------------------------------------------------
# mean_timedelta
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "values,expected",
    [
        ([], None),
        ([None, None], None),
        ([timedelta(hours=2)], timedelta(hours=2)),
        ([timedelta(hours=2), None], timedelta(hours=2)),
        ([timedelta(hours=2), timedelta(hours=4)], timedelta(hours=3)),
        ([None, timedelta(hours=6), timedelta(hours=12)], timedelta(hours=9)),
    ],
)
def test_mean_timedelta(values, expected):
    assert mean_timedelta(values) == expected


# ---------------------------------------------------------------------------
# direction
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "prior,current,expected",
    [
        (None, None, "same"),
        (None, 5, "same"),
        (5, None, "same"),
        (3, 5, "up"),
        (5, 3, "down"),
        (4, 4, "same"),
        (timedelta(hours=2), timedelta(hours=4), "up"),
        (timedelta(hours=4), timedelta(hours=2), "down"),
        (timedelta(hours=3), timedelta(hours=3), "same"),
        (timedelta(hours=2), None, "same"),
        (None, timedelta(hours=2), "same"),
    ],
)
def test_direction(prior, current, expected):
    assert direction(prior, current) == expected


# ---------------------------------------------------------------------------
# build_period_stats
# ---------------------------------------------------------------------------


def test_build_period_stats_empty():
    stats = build_period_stats([], "2026-01-01", "2026-02-12")
    assert stats.total_incidents == 0
    assert stats.top_entities == []
    assert stats.severity_counts == {"S1": 0.0, "S2": 0.0, "S3": 0.0, "S4": 0.0}
    assert stats.status_counts == {
        "Detected": 0.0,
        "InProgress": 0.0,
        "Mitigated": 0.0,
        "Resolved": 0.0,
    }
    assert stats.service_mean_tt_dec is None
    assert stats.service_mean_tt_alert is None
    assert stats.service_mean_tt_mit is None
    assert stats.service_mean_tt_res is None
    assert stats.product_mean_tt_dec is None
    assert stats.product_mean_tt_res is None


def test_build_period_stats_total():
    incidents = [make_incident(key=f"IIM-{i}") for i in range(5)]
    stats = build_period_stats(incidents, "2026-01-01", "2026-02-12")
    assert stats.total_incidents == 5


def test_build_period_stats_total_entities():
    incidents = [
        make_incident(key="IIM-1", entities="auth, payments"),
        make_incident(key="IIM-2", entities="auth"),  # auth already counted
        make_incident(key="IIM-3", entities="unknown"),  # excluded
        make_incident(key="IIM-4", entities=None),  # excluded
    ]
    stats = build_period_stats(incidents, "2026-01-01", "2026-02-12")
    assert stats.total_entities == 2  # auth, payments


@pytest.mark.parametrize(
    "entities,expected_top",
    [
        (["payments"], [("payments", 1)]),
        (["auth", "auth"], [("auth", 2)]),
        (["unknown", "payments"], [("payments", 1)]),
        ([None, "payments"], [("payments", 1)]),
        # tie broken alphabetically
        (["beta", "alpha"], [("alpha", 1), ("beta", 1)]),
        # top 5 cap: sorted alphabetically when all tied at 1
        (
            ["g", "f", "e", "d", "c", "b", "a"],
            [("a", 1), ("b", 1), ("c", 1), ("d", 1), ("e", 1)],
        ),
    ],
)
def test_build_period_stats_top_entities(entities, expected_top):
    incidents = [
        make_incident(key=f"IIM-{i}", entities=e) for i, e in enumerate(entities)
    ]
    stats = build_period_stats(incidents, "2026-01-01", "2026-02-12")
    assert stats.top_entities == expected_top


def test_build_period_stats_top_entities_multi_entity():
    # one incident with two entities counts once per entity
    incidents = [make_incident(entities="payments, auth")]
    stats = build_period_stats(incidents, "2026-01-01", "2026-02-12")
    assert ("payments", 1) in stats.top_entities
    assert ("auth", 1) in stats.top_entities


@pytest.mark.parametrize(
    "severities,expected",
    [
        # 3 incidents: S1=2, S2=1 → 66.7%, 33.3%, 0%, 0%
        (
            ["S1", "S1", "S2"],
            {
                "S1": approx(66.67, rel=1e-2),
                "S2": approx(33.33, rel=1e-2),
                "S3": 0.0,
                "S4": 0.0,
            },
        ),
        # 1 incident: S4=100%
        (["S4"], {"S1": 0.0, "S2": 0.0, "S3": 0.0, "S4": 100.0}),
        # 2 incidents: S1=1 → 50%
        ([None, "S1"], {"S1": 50.0, "S2": 0.0, "S3": 0.0, "S4": 0.0}),
        # 1 incident with unrecognized severity → all 0%
        (["undetermined"], {"S1": 0.0, "S2": 0.0, "S3": 0.0, "S4": 0.0}),
    ],
)
def test_build_period_stats_severity_counts(severities, expected):
    incidents = [
        make_incident(key=f"IIM-{i}", severity=s) for i, s in enumerate(severities)
    ]
    stats = build_period_stats(incidents, "2026-01-01", "2026-02-12")
    assert stats.severity_counts == expected


@pytest.mark.parametrize(
    "statuses,expected",
    [
        (
            ["Resolved", "Resolved", "Detected"],
            {
                "Detected": approx(33.33, rel=1e-2),
                "InProgress": 0.0,
                "Mitigated": 0.0,
                "Resolved": approx(66.67, rel=1e-2),
            },
        ),
        (
            ["InProgress"],
            {"Detected": 0.0, "InProgress": 100.0, "Mitigated": 0.0, "Resolved": 0.0},
        ),
    ],
)
def test_build_period_stats_status_counts(statuses, expected):
    incidents = [
        make_incident(
            key=f"IIM-{i}",
            status=s,
            resolved=("2026-01-15 12:00" if s == "Resolved" else None),
        )
        for i, s in enumerate(statuses)
    ]
    stats = build_period_stats(incidents, "2026-01-01", "2026-02-12")
    assert stats.status_counts == expected


def test_build_period_stats_tt_res_resolved_only():
    # incident with resolved timestamp but status != "Resolved" excluded from TT-RES
    resolved_incident = make_incident(
        key="IIM-1",
        status="Resolved",
        impact_start="2026-01-15 10:00",
        resolved="2026-01-15 14:00",
    )
    not_resolved_incident = make_incident(
        key="IIM-2",
        status="Mitigated",
        impact_start="2026-01-15 10:00",
        resolved="2026-01-15 16:00",
    )
    stats = build_period_stats(
        [resolved_incident, not_resolved_incident], "2026-01-01", "2026-02-12"
    )
    # only resolved_incident contributes: 4h
    assert stats.service_mean_tt_res == timedelta(hours=4)


def test_build_period_stats_mean_action_items():
    from iim.libreport import ActionItem

    resolved_2 = make_incident(
        key="IIM-1",
        status="Resolved",
        action_items=[
            ActionItem(url="https://jira.example.net/browse/OA-1"),
            ActionItem(url="https://jira.example.net/browse/OA-2"),
        ],
    )
    resolved_4 = make_incident(
        key="IIM-2",
        status="Resolved",
        action_items=[
            ActionItem(url=f"https://jira.example.net/browse/OA-{i}") for i in range(4)
        ],
    )
    # unresolved — excluded from mean
    active = make_incident(
        key="IIM-3",
        status="InProgress",
        action_items=[ActionItem(url="https://jira.example.net/browse/OA-9")],
    )
    # resolved but action_items=None — excluded from mean
    resolved_none = make_incident(key="IIM-4", status="Resolved", action_items=None)

    stats = build_period_stats(
        [resolved_2, resolved_4, active, resolved_none], "2026-01-01", "2026-02-12"
    )
    assert stats.mean_action_items == 3.0  # (2 + 4) / 2


def test_build_period_stats_mean_action_items_none_when_no_resolved():
    stats = build_period_stats(
        [make_incident(status="InProgress", action_items=None)],
        "2026-01-01",
        "2026-02-12",
    )
    assert stats.mean_action_items is None


def test_build_period_stats_entity_bucket_split():
    # "auth" -> service bucket, "firefox" -> product bucket
    service_incident = make_incident(
        key="IIM-1",
        entities="auth",
        impact_start="2026-01-15 10:00",
        mitigated="2026-01-15 12:00",
    )
    product_incident = make_incident(
        key="IIM-2",
        entities="firefox",
        impact_start="2026-01-15 10:00",
        mitigated="2026-01-15 13:00",
    )
    stats = build_period_stats(
        [service_incident, product_incident], "2026-01-01", "2026-02-12"
    )
    assert stats.service_mean_tt_mit == timedelta(hours=2)
    assert stats.product_mean_tt_mit == timedelta(hours=3)


# ---------------------------------------------------------------------------
# compute_period_comparison
# ---------------------------------------------------------------------------


def test_compute_period_comparison_period_boundaries():
    # this_friday=2026-03-27: current 2026-02-13..2026-03-27, prior 2026-01-02..2026-02-13
    comparison = compute_period_comparison(
        [], "2026-02-13", "2026-03-27", "2026-01-02", "2026-02-13"
    )
    assert comparison.current.start == "2026-02-13"
    assert comparison.current.end == "2026-03-27"
    assert comparison.prior.start == "2026-01-02"
    assert comparison.prior.end == "2026-02-13"


def test_compute_period_comparison_period_filtering():
    # current 2026-02-13..2026-03-27, prior 2026-01-02..2026-02-13
    current_incident = make_incident(key="IIM-1", declare_date="2026-03-01")
    prior_incident = make_incident(key="IIM-2", declare_date="2026-01-15")
    outside_incident = make_incident(key="IIM-3", declare_date="2025-12-01")
    no_date_incident = make_incident(key="IIM-4", declare_date=None)

    comparison = compute_period_comparison(
        [current_incident, prior_incident, outside_incident, no_date_incident],
        "2026-02-13",
        "2026-03-27",
        "2026-01-02",
        "2026-02-13",
    )
    assert comparison.current.total_incidents == 1
    assert comparison.prior.total_incidents == 1


def test_compute_period_comparison_boundary_inclusive_start():
    # incident exactly on current_start belongs to current, not prior
    comparison = compute_period_comparison(
        [make_incident(key="IIM-1", declare_date="2026-02-13")],
        "2026-02-13",
        "2026-03-27",
        "2026-01-02",
        "2026-02-13",
    )
    assert comparison.current.total_incidents == 1
    assert comparison.prior.total_incidents == 0


def test_compute_period_comparison_boundary_exclusive_end():
    # incident on current_end belongs to neither period (end is exclusive)
    comparison = compute_period_comparison(
        [make_incident(key="IIM-1", declare_date="2026-03-27")],
        "2026-02-13",
        "2026-03-27",
        "2026-01-02",
        "2026-02-13",
    )
    assert comparison.current.total_incidents == 0
    assert comparison.prior.total_incidents == 0


def test_compute_period_comparison_empty():
    comparison = compute_period_comparison(
        [], "2026-02-13", "2026-03-27", "2026-01-02", "2026-02-13"
    )
    assert comparison.current.total_incidents == 0
    assert comparison.prior.total_incidents == 0
