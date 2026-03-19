# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from dataclasses import dataclass
import re
from typing import Any, Optional


JIRA_KEY_RE = re.compile(r"https?://[^\s/]+/browse/([A-Z][A-Z0-9]+-\d+)")


def jira_key(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    match = JIRA_KEY_RE.match(url)
    if match:
        return match[1]
    return None


GITHUB_ISSUE_ID_RE = re.compile(
    r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/issues/\d+)"
)
GITHUB_PR_ID_RE = re.compile(
    r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/pull/\d+)"
)


def github_id(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    match = GITHUB_ISSUE_ID_RE.match(url)
    if match:
        return match[1]
    match = GITHUB_PR_ID_RE.match(url)
    if match:
        return match[1]
    return None


BUGZILLA_ID_RE = re.compile(r"https?://[^\s/]+/show_bug\.cgi\?id=(\d+)")


def bugzilla_id(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    match = BUGZILLA_ID_RE.match(url)
    if match:
        return match[1]
    return None


ESSENCE_RE = re.compile(r"action: \[([^\]]+)\] (\S+) (.*)")


@dataclass
class ActionItem:
    url: Optional[str] = None
    status: Optional[str] = None
    title: Optional[str] = None
    # Jira issue link ID (for removal from Jira)
    jira_id: Optional[str] = None

    def tracker(self) -> Optional[str]:
        if jira_key(self.url):
            return "jira"
        if bugzilla_id(self.url):
            return "bugzilla"
        if github_id(self.url):
            return "github"
        return None

    @staticmethod
    def is_changed(
        old_data: Optional["ActionItem"], new_data: Optional["ActionItem"]
    ) -> bool:
        if old_data is None or new_data is None:
            return True
        if old_data.url != new_data.url:
            return True
        # If they're Jira urls, then we ignore the title and status since Jira
        # will tell us the updated data
        if old_data.tracker() == "jira":
            return False
        return old_data.title != new_data.title or old_data.status != new_data.status

    def essence(self) -> Optional[str]:
        # Essence of a jira action item is the key
        if jira_key(self.url):
            return jira_key(self.url)
        # Essence of a non-jira action items is "[status] url: title"
        return f"action: [{self.status}] {self.url} {self.title}"

    @classmethod
    def from_essence(cls, url, title, jira_id=None):
        match = ESSENCE_RE.match(title)
        if match is None:
            return None

        return cls(
            url=url,
            status=match[1],
            title=match[3],
            jira_id=jira_id,
        )


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
    # action items
    action_items: Optional[list[ActionItem]] = None
    # incident report template version (e.g. "2026.03.12")
    template_version: Optional[str] = None
    # computed timing fields populated by iim_weekly_overview
    tt_dec: Optional[str] = None
    tt_alert: Optional[str] = None
    tt_mit: Optional[str] = None

    @property
    def tracked_action_items(self):
        return [item for item in self.action_items or [] if item.url]
