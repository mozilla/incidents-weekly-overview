# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import pytest

from iim.libgdoc import BadGdocId, download_gdoc, extract_doc_id, get_doc_modified_time
from iim.libreport import IncidentReport
from iim.libgdoc import update_report


# ---------------------------------------------------------------------------
# extract_doc_id
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url, expected",
    [
        (
            "https://docs.google.com/document/d/1O0KXJlklGcQzr2CYb3MTGyS_ZO2B3R0x532bPaxXyL4/edit",
            "1O0KXJlklGcQzr2CYb3MTGyS_ZO2B3R0x532bPaxXyL4",
        ),
        (
            "https://docs.google.com/document/d/ABC123/edit?usp=sharing",
            "ABC123",
        ),
        (
            "https://docs.google.com/document/d/ABC-123_xyz/view",
            "ABC-123_xyz",
        ),
    ],
)
def test_extract_doc_id_valid(url, expected):
    assert extract_doc_id(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://example.net/not-a-doc",
        "https://docs.google.com/spreadsheets/d/ABC123/edit",
        "no doc",
        "",
    ],
)
def test_extract_doc_id_invalid(url):
    with pytest.raises(ValueError, match="Could not extract document ID"):
        extract_doc_id(url)


# ---------------------------------------------------------------------------
# download_gdoc — bad URL raises BadGdocId without touching the service
# ---------------------------------------------------------------------------


def test_download_gdoc_bad_url_raises():
    with pytest.raises(BadGdocId):
        download_gdoc(None, "https://example.net/not-a-doc")


# ---------------------------------------------------------------------------
# get_doc_modified_time — guard clauses that never touch the Drive service
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "drive_service, report_url",
    [
        (None, "https://docs.google.com/document/d/ABC123/edit"),
        (object(), None),
        (object(), ""),
        (object(), "no doc"),
        # Valid-looking object but non-doc URL: extract_doc_id raises ValueError,
        # which is caught and returns None without calling the service.
        (object(), "https://example.net/not-a-doc"),
    ],
)
def test_get_doc_modified_time_returns_none(drive_service, report_url):
    assert get_doc_modified_time(drive_service, report_url) is None


# ---------------------------------------------------------------------------
# update_report — guard clauses that never touch the Drive service
# ---------------------------------------------------------------------------


def test_update_report_no_service_leaves_report_unchanged():
    report = IncidentReport(
        key="IIM-1",
        report_url="https://docs.google.com/document/d/ABC123/edit",
    )
    result = update_report(None, report)
    assert result is report
    assert result.report_modified is None


def test_update_report_no_report_url_leaves_report_unchanged():
    report = IncidentReport(key="IIM-1", report_url=None)
    result = update_report(object(), report)
    assert result is report
    assert result.report_modified is None
