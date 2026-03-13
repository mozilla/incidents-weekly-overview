# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class IncidentReport:
    key: Optional[str] = None
    jira_url: Optional[str] = None
    report_url: Optional[str] = None
    summary: Optional[str] = None
    # FIXME(willkg): this is an ADF structure from Jira; we should figure out
    # how to handle this better
    description: Optional[Any] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    entities: Optional[str] = None
    detection_method: Optional[str] = None
    # date in UTC in YYYY-MM-DD format
    declare_date: Optional[str] = None
    # timestamps in UTC in YYYY-MM-DD HH:MM format
    impact_start: Optional[str] = None
    declared: Optional[str] = None
    detected: Optional[str] = None  # deprecated 2026-03-12
    alerted: Optional[str] = None
    acknowledged: Optional[str] = None
    responded: Optional[str] = None
    mitigated: Optional[str] = None
    resolved: Optional[str] = None
    # computed timing fields populated by iim_weekly_overview
    tt_dec: Optional[str] = None
    tt_alert: Optional[str] = None
    tt_mit: Optional[str] = None
