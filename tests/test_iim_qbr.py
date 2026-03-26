# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from datetime import timedelta

import arrow
import pytest

from iim.iim_qbr import (
    get_start_end,
    pct_change,
)
from iim.libstats import humanize_timedelta


# ---------------------------------------------------------------------------
# humanize_timedelta
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "td, expected",
    [
        (None, "?"),
        (timedelta(seconds=0), "0s"),
        (timedelta(seconds=30), "30s"),
        (timedelta(minutes=1), "1m"),
        (timedelta(hours=1), "1h"),
        (timedelta(hours=1, minutes=30), "1h 30m"),
        (timedelta(days=1), "1d"),
        (timedelta(days=1, hours=1), "1d 1h"),
        # only 2 most significant parts
        (timedelta(minutes=100000), "69d 10h"),
        (timedelta(minutes=-30), "-30m"),
        (timedelta(minutes=-90), "-1h 30m"),
    ],
)
def test_humanize_timedelta(td, expected):
    assert humanize_timedelta(td) == expected


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
