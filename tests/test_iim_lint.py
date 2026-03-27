# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import pytest

from iim.iim_lint import (
    FutureTimestampLintRule,
    MismatchedDeclareDateLintRule,
    MissingActionItemsLintRule,
    MissingDatesLintRule,
    MissingEntitiesLintRule,
    MissingMitigatedLintRule,
    MissingResolvedLintRule,
    WrongStatusLintRule,
    _issue_key_num,
)
from iim.libreport import IncidentReport


# ---------------------------------------------------------------------------
# _issue_key_num
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "key, expected",
    [
        ("IIM-1", 1),
        ("IIM-9", 9),
        ("IIM-131", 131),
        ("IIM-1000", 1000),
    ],
)
def test_issue_key_num(key, expected):
    assert _issue_key_num(key) == expected


# ---------------------------------------------------------------------------
# LR010 MissingResolvedLintRule
# ---------------------------------------------------------------------------


def test_missing_resolved_passes_when_resolved_and_has_timestamp():
    report = IncidentReport(key="IIM-1", status="Resolved", resolved="2026-01-01 10:00")
    assert MissingResolvedLintRule().lint(report) is None


def test_missing_resolved_passes_when_not_resolved():
    report = IncidentReport(key="IIM-1", status="In Progress", resolved=None)
    assert MissingResolvedLintRule().lint(report) is None


def test_missing_resolved_fails_when_resolved_status_no_timestamp():
    report = IncidentReport(key="IIM-1", status="Resolved", resolved=None)
    msg = MissingResolvedLintRule().lint(report)
    assert msg == 'Status is "Resolved" but resolved timestamp is not set.'


def test_missing_resolved_fails_when_resolved_status_empty_timestamp():
    report = IncidentReport(key="IIM-1", status="Resolved", resolved="")
    msg = MissingResolvedLintRule().lint(report)
    assert msg == 'Status is "Resolved" but resolved timestamp is not set.'


# ---------------------------------------------------------------------------
# LR020 MissingMitigatedLintRule
# ---------------------------------------------------------------------------


def test_missing_mitigated_passes_when_mitigated_and_has_timestamp():
    report = IncidentReport(
        key="IIM-1", status="Mitigated", mitigated="2026-01-01 10:00"
    )
    assert MissingMitigatedLintRule().lint(report) is None


def test_missing_mitigated_passes_when_not_mitigated():
    report = IncidentReport(key="IIM-1", status="In Progress", mitigated=None)
    assert MissingMitigatedLintRule().lint(report) is None


def test_missing_mitigated_fails_when_mitigated_status_no_timestamp():
    report = IncidentReport(key="IIM-1", status="Mitigated", mitigated=None)
    msg = MissingMitigatedLintRule().lint(report)
    assert msg == 'Status is "Mitigated" but mitigated timestamp is not set.'


def test_missing_mitigated_fails_when_mitigated_status_empty_timestamp():
    report = IncidentReport(key="IIM-1", status="Mitigated", mitigated="")
    msg = MissingMitigatedLintRule().lint(report)
    assert msg == 'Status is "Mitigated" but mitigated timestamp is not set.'


# ---------------------------------------------------------------------------
# LR030 WrongStatusLintRule
# ---------------------------------------------------------------------------


def test_wrong_status_passes_resolved_with_correct_status():
    report = IncidentReport(key="IIM-1", status="Resolved", resolved="2026-01-01 10:00")
    assert WrongStatusLintRule().lint(report) is None


def test_wrong_status_passes_mitigated_with_mitigated_status():
    report = IncidentReport(
        key="IIM-1", status="Mitigated", mitigated="2026-01-01 10:00"
    )
    assert WrongStatusLintRule().lint(report) is None


def test_wrong_status_passes_mitigated_with_resolved_status():
    report = IncidentReport(
        key="IIM-1",
        status="Resolved",
        mitigated="2026-01-01 09:00",
        resolved="2026-01-01 10:00",
    )
    assert WrongStatusLintRule().lint(report) is None


def test_wrong_status_passes_no_timestamps():
    report = IncidentReport(key="IIM-1", status="In Progress")
    assert WrongStatusLintRule().lint(report) is None


def test_wrong_status_fails_resolved_timestamp_wrong_status():
    report = IncidentReport(
        key="IIM-1", status="In Progress", resolved="2026-01-01 10:00"
    )
    msg = WrongStatusLintRule().lint(report)
    assert msg == 'Has resolved timestamp but status is "In Progress".'


def test_wrong_status_fails_mitigated_timestamp_wrong_status():
    report = IncidentReport(
        key="IIM-1", status="In Progress", mitigated="2026-01-01 10:00"
    )
    msg = WrongStatusLintRule().lint(report)
    assert msg == 'Has mitigated timestamp but status is "In Progress".'


def test_wrong_status_fails_both_timestamps_wrong_status():
    report = IncidentReport(
        key="IIM-1",
        status="In Progress",
        mitigated="2026-01-01 09:00",
        resolved="2026-01-01 10:00",
    )
    msg = WrongStatusLintRule().lint(report)
    assert msg == (
        'Has resolved timestamp but status is "In Progress". '
        'Has mitigated timestamp but status is "In Progress".'
    )


# ---------------------------------------------------------------------------
# LR040 MissingEntitiesLintRule
# ---------------------------------------------------------------------------


def test_missing_entities_passes_when_entities_set():
    report = IncidentReport(key="IIM-1", entities="firefox")
    assert MissingEntitiesLintRule().lint(report) is None


def test_missing_entities_fails_when_entities_none():
    report = IncidentReport(key="IIM-1", entities=None)
    assert MissingEntitiesLintRule().lint(report) == "Entities is not set."


# ---------------------------------------------------------------------------
# LR050 MissingDatesLintRule
# ---------------------------------------------------------------------------


def test_missing_dates_passes_when_both_set():
    report = IncidentReport(
        key="IIM-1", declare_date="2026-01-01", declared="2026-01-01 10:00"
    )
    assert MissingDatesLintRule().lint(report) is None


def test_missing_dates_fails_when_declare_date_missing():
    report = IncidentReport(key="IIM-1", declare_date=None, declared="2026-01-01 10:00")
    assert MissingDatesLintRule().lint(report) == "declare_date is not set."


def test_missing_dates_fails_when_declared_missing():
    report = IncidentReport(key="IIM-1", declare_date="2026-01-01", declared=None)
    assert MissingDatesLintRule().lint(report) == "declared is not set."


def test_missing_dates_fails_when_both_missing():
    report = IncidentReport(key="IIM-1", declare_date=None, declared=None)
    assert (
        MissingDatesLintRule().lint(report)
        == "declare_date is not set. declared is not set."
    )


# ---------------------------------------------------------------------------
# LR060 MismatchedDeclareDateLintRule
# ---------------------------------------------------------------------------


def test_mismatched_declare_date_passes_when_dates_match():
    report = IncidentReport(
        key="IIM-1", declare_date="2026-01-01", declared="2026-01-01 10:00"
    )
    assert MismatchedDeclareDateLintRule().lint(report) is None


def test_mismatched_declare_date_skips_when_declare_date_missing():
    report = IncidentReport(key="IIM-1", declare_date=None, declared="2026-01-01 10:00")
    assert MismatchedDeclareDateLintRule().lint(report) is None


def test_mismatched_declare_date_skips_when_declared_missing():
    report = IncidentReport(key="IIM-1", declare_date="2026-01-01", declared=None)
    assert MismatchedDeclareDateLintRule().lint(report) is None


def test_mismatched_declare_date_fails_when_dates_differ():
    report = IncidentReport(
        key="IIM-1", declare_date="2026-01-02", declared="2026-01-01 10:00"
    )
    assert MismatchedDeclareDateLintRule().lint(report) == (
        "declare_date '2026-01-02' does not match date portion of declared '2026-01-01'."
    )


# ---------------------------------------------------------------------------
# LR070 MissingActionItemsLintRule
# ---------------------------------------------------------------------------


def test_missing_action_items_passes_when_resolved_with_action_items():
    from iim.libreport import ActionItem

    report = IncidentReport(
        key="IIM-1",
        status="Resolved",
        action_items=[ActionItem(url="https://github.com/mozilla/foo/issues/1")],
    )
    assert MissingActionItemsLintRule().lint(report) is None


def test_missing_action_items_passes_when_not_resolved():
    report = IncidentReport(key="IIM-1", status="In Progress", action_items=[])
    assert MissingActionItemsLintRule().lint(report) is None


def test_missing_action_items_fails_when_resolved_with_no_action_items():
    report = IncidentReport(key="IIM-1", status="Resolved", action_items=[])
    assert MissingActionItemsLintRule().lint(report) == (
        'Status is "Resolved" but there are no action items.'
    )


def test_missing_action_items_fails_when_resolved_with_none_action_items():
    report = IncidentReport(key="IIM-1", status="Resolved", action_items=None)
    assert MissingActionItemsLintRule().lint(report) == (
        'Status is "Resolved" but there are no action items.'
    )


# ---------------------------------------------------------------------------
# LR080 UndeterminedSeverityLintRule
# ---------------------------------------------------------------------------


def test_undetermined_severity_passes_when_severity_set():
    from iim.iim_lint import UndeterminedSeverityLintRule

    report = IncidentReport(key="IIM-1", severity="S2")
    assert UndeterminedSeverityLintRule().lint(report) is None


def test_undetermined_severity_fails_when_severity_undetermined():
    from iim.iim_lint import UndeterminedSeverityLintRule

    report = IncidentReport(key="IIM-1", severity="undetermined")
    assert UndeterminedSeverityLintRule().lint(report) == 'Severity is "undetermined".'


# ---------------------------------------------------------------------------
# LR090 FutureTimestampLintRule
# ---------------------------------------------------------------------------

PAST = "2026-01-01 10:00"
FUTURE = "2099-01-01 00:00"
FUTURE_DATE = "2099-01-01"


def test_future_timestamp_passes_when_all_fields_none():
    report = IncidentReport(key="IIM-1")
    assert FutureTimestampLintRule().lint(report) is None


def test_future_timestamp_passes_when_all_fields_in_past():
    report = IncidentReport(
        key="IIM-1",
        declare_date="2026-01-01",
        impact_start=PAST,
        declared=PAST,
        detected=PAST,
        alerted=PAST,
        acknowledged=PAST,
        responded=PAST,
        mitigated=PAST,
        resolved=PAST,
    )
    assert FutureTimestampLintRule().lint(report) is None


@pytest.mark.parametrize(
    "field, value",
    [
        ("declare_date", FUTURE_DATE),
        ("impact_start", FUTURE),
        ("declared", FUTURE),
        ("detected", FUTURE),
        ("alerted", FUTURE),
        ("acknowledged", FUTURE),
        ("responded", FUTURE),
        ("mitigated", FUTURE),
        ("resolved", FUTURE),
    ],
)
def test_future_timestamp_fails_when_single_field_in_future(field, value):
    report = IncidentReport(key="IIM-1", **{field: value})
    msg = FutureTimestampLintRule().lint(report)
    assert msg == f"Fields set to future timestamps: {field}."


def test_future_timestamp_fails_when_multiple_fields_in_future():
    report = IncidentReport(key="IIM-1", alerted=FUTURE, resolved=FUTURE)
    msg = FutureTimestampLintRule().lint(report)
    assert msg == "Fields set to future timestamps: alerted, resolved."
