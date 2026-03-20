# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import arrow
import pytest

from iim.iim_qbr import (
    Stats,
    get_review_stats,
    get_start_end,
    get_stats,
    humanize,
    pct_change,
)
from iim.libreport import IncidentReport


def make_incident(**kwargs):
    defaults = dict(
        key="IIM-1",
        severity="S3",
        detection_method="Automation",
        impact_start="2025-06-01 10:00:00",
    )
    return IncidentReport(**{**defaults, **kwargs})


# ---------------------------------------------------------------------------
# humanize
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "total_minutes, expected",
    [
        (0, "0s"),
        (0.5, "30s"),
        (1, "1m"),
        (60, "1h"),
        (90, "1h 30m"),
        (1440, "1d"),
        (1500, "1d 1h"),
        # only 2 most significant parts
        (100000, "69d 10h"),
        (-30, "-30m"),
        (-90, "-1h 30m"),
    ],
)
def test_humanize(total_minutes, expected):
    assert humanize(total_minutes) == expected


# ---------------------------------------------------------------------------
# get_start_end
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "year, quarter, expected_start, expected_end",
    [
        (2025, 1, "2025-01-01 00:00:00", "2025-03-31 23:59:59"),
        (2025, 2, "2025-04-01 00:00:00", "2025-06-30 23:59:59"),
        (2025, 3, "2025-07-01 00:00:00", "2025-09-30 23:59:59"),
        (2025, 4, "2025-10-01 00:00:00", "2025-12-31 23:59:59"),
    ],
)
def test_get_start_end(year, quarter, expected_start, expected_end):
    start, end = get_start_end(year, quarter)
    assert start == arrow.get(expected_start)
    assert end == arrow.get(expected_end)


def test_get_start_end_invalid_quarter():
    with pytest.raises(ValueError):
        get_start_end(2025, 5)


# ---------------------------------------------------------------------------
# pct_change
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "a, b, expected",
    [
        (100, 150, 50.0),
        (100, 50, -50.0),
        (100, 100, 0.0),
        (0, 50, -1),
        (0, 0, -1),
    ],
)
def test_pct_change(a, b, expected):
    assert pct_change(a, b) == expected


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


def test_get_stats_severity_breakdown():
    incidents = [
        make_incident(key="IIM-1", severity="S1"),
        make_incident(key="IIM-2", severity="S2"),
        make_incident(key="IIM-3", severity="S2"),
        make_incident(key="IIM-4", severity="S3"),
    ]
    stats = get_stats(incidents)
    assert stats.total == 4
    assert stats.s1 == 1
    assert stats.s2 == 2
    assert stats.s3 == 1
    assert stats.s4 == 0
    assert stats.s1s2_incidents == 3


def test_get_stats_detection_breakdown():
    incidents = [
        make_incident(key="IIM-1", detection_method="Automation"),
        make_incident(key="IIM-2", detection_method="Automation"),
        make_incident(key="IIM-3", detection_method="Manual"),
    ]
    stats = get_stats(incidents)
    assert stats.automation == 2
    assert stats.manual == 1


def test_get_stats_timing():
    incidents = [
        make_incident(
            key="IIM-1",
            impact_start="2025-06-01 10:00:00",
            alerted="2025-06-01 10:10:00",  # 10 minutes
            responded="2025-06-01 10:20:00",  # 20 minutes
            mitigated="2025-06-01 11:00:00",  # 60 minutes
        ),
    ]
    stats = get_stats(incidents)
    assert stats.tt_alerted == [10.0]
    assert stats.tt_responded == [20.0]
    assert stats.tt_mitigated == [60.0]


def test_get_stats_alerted_falls_back_to_detected():
    incidents = [
        make_incident(
            key="IIM-1",
            impact_start="2025-06-01 10:00:00",
            alerted=None,
            detected="2025-06-01 10:05:00",  # 5 minutes
        ),
    ]
    stats = get_stats(incidents)
    assert stats.tt_alerted == [5.0]


def test_get_stats_skips_no_impact_start():
    incidents = [
        make_incident(key="IIM-1", impact_start=None),  # skipped in breakdown
        make_incident(key="IIM-2", severity="S2"),
    ]
    stats = get_stats(incidents)
    assert stats.total == 2
    assert stats.s2 == 1
    assert stats.s3 == 0  # IIM-1 (S3) was skipped


def test_get_stats_skips_excessive_response_time():
    incidents = [
        make_incident(
            key="IIM-1",
            impact_start="2025-06-01 10:00:00",
            responded="2030-01-01 10:00:00",  # years later, well over 1800000s
        ),
    ]
    stats = get_stats(incidents)
    assert stats.tt_responded == []
    assert stats.s3 == 0  # skipped entirely from breakdown


def test_get_stats_entities():
    incidents = [
        make_incident(key="IIM-1", entities="Firefox, Fenix"),
        make_incident(key="IIM-2", entities="Relay"),
    ]
    stats = get_stats(incidents)
    assert stats.entities == {"firefox", "fenix", "relay"}


def test_get_stats_entities_lowercased_and_stripped():
    incidents = [
        make_incident(key="IIM-1", entities="  FIREFOX ,  Fenix  "),
    ]
    stats = get_stats(incidents)
    assert "firefox" in stats.entities
    assert "fenix" in stats.entities


# ---------------------------------------------------------------------------
# get_review_stats
# ---------------------------------------------------------------------------

REVIEW_DATA = {
    "2025-04-15": ["IIM-10", "IIM-11"],
    "2025-07-10": ["IIM-20", "IIM-21"],
    "2025-10-05": ["IIM-30"],
}


def test_get_review_stats_counts_reviews_in_range():
    date_start = arrow.get("2025-04-01 00:00:00")
    date_end = arrow.get("2025-06-30 23:59:59")
    incidents = [
        make_incident(key="IIM-10", severity="S2"),
        make_incident(key="IIM-11", severity="S3"),
    ]
    stats = get_review_stats(Stats(), date_start, date_end, incidents, REVIEW_DATA)
    assert stats.number_reviewed == 2


def test_get_review_stats_s1s2_reviewed():
    date_start = arrow.get("2025-04-01 00:00:00")
    date_end = arrow.get("2025-06-30 23:59:59")
    incidents = [
        make_incident(key="IIM-10", severity="S2"),
        make_incident(key="IIM-11", severity="S3"),
    ]
    stats = get_review_stats(Stats(), date_start, date_end, incidents, REVIEW_DATA)
    assert stats.s1s2_reviewed == 1  # only IIM-10 is S2


def test_get_review_stats_excludes_meetings_outside_range():
    date_start = arrow.get("2025-07-01 00:00:00")
    date_end = arrow.get("2025-09-30 23:59:59")
    incidents = [
        make_incident(key="IIM-10", severity="S2"),  # reviewed at out-of-range meeting
        make_incident(key="IIM-20", severity="S1"),  # reviewed at in-range meeting
    ]
    stats = get_review_stats(Stats(), date_start, date_end, incidents, REVIEW_DATA)
    assert stats.number_reviewed == 2  # IIM-20, IIM-21 from 2025-07-10 meeting
    assert stats.s1s2_reviewed == 1  # only IIM-20 (S1) is in the reviewed set


def test_get_review_stats_no_meetings_in_range():
    date_start = arrow.get("2026-01-01 00:00:00")
    date_end = arrow.get("2026-03-31 23:59:59")
    incidents = [make_incident(key="IIM-10")]
    stats = get_review_stats(Stats(), date_start, date_end, incidents, REVIEW_DATA)
    assert stats.number_reviewed == 0
    assert stats.s1s2_reviewed == 0
