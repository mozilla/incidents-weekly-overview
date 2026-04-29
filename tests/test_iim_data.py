# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from datetime import timedelta

import arrow
import click
import pytest

from iim.iim_data import parse_period


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
    naive_30day = arrow.now().shift(days=-30)
    result = parse_period("1mo")
    # Should be much closer to the calendar shift than to a 30-day shift
    # (except in February, where they're closer; the gap is still detectable).
    assert abs(result - cal_expected) < timedelta(seconds=5)
    # Sanity: in months that aren't 30 days, the two cutoffs differ.
    if cal_expected != naive_30day:
        assert abs(result - naive_30day) > timedelta(hours=1)


def test_parse_period_calendar_aware_years():
    """Years use calendar math (handles leap years)."""
    expected = arrow.now().shift(years=-1)
    result = parse_period("1y")
    assert abs(result - expected) < timedelta(seconds=5)
