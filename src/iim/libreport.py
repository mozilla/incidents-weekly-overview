# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from dataclasses import dataclass
from datetime import timedelta
import json
from importlib.resources import files as resources_files
import re
from typing import Any, Optional

import arrow


ENTITY_BUCKET: dict[str, str] = json.loads(
    (resources_files("iim") / "data" / "service_product_entity_bucket.json").read_text()
)


JIRA_KEY_RE = re.compile(r"https?://[^\s/]+/browse/([A-Z][A-Z0-9]+-\d+)")
JIRA_KEY_BARE_RE = re.compile(r"^([A-Z][A-Z0-9]+-\d+)$")


def jira_key(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    match = JIRA_KEY_RE.match(url)
    if match:
        return match[1]
    match = JIRA_KEY_BARE_RE.match(url)
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


def normalize_entities(value: str | None) -> str | None:
    """Normalize a comma-separated entities string to sorted, lowercased, ', '-delimited form."""
    if not value or not value.strip():
        return None
    parts = [p.strip().lower() for p in value.split(",") if p.strip()]
    return ", ".join(sorted(parts))


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
        key = jira_key(self.url)
        if key:
            return key
        # Essence of a non-jira action items is "[status] url: title"
        return f"action: [{self.status}] {self.url} {self.title}"[:254]

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
    report_modified: Optional[str] = None
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

    @property
    def _start_ts(self) -> Optional[str]:
        return self.impact_start or self.detected

    @property
    def entity_bucket(self) -> str:
        """Returns one of 'service', 'product', or 'unknown'"""
        if not self.entities:
            return "unknown"
        for item in self.entities.split(","):
            item = item.strip().lower()
            if ENTITY_BUCKET.get(item, "service") == "service":
                return "service"

        return "product"

    @property
    def age(self) -> Optional[timedelta]:
        start_ts = self.impact_start or self.declared
        if not start_ts:
            return None
        end_ts = arrow.get(self.resolved) if self.resolved else arrow.now()
        return end_ts - arrow.get(start_ts)

    @property
    def tt_declared(self) -> Optional[timedelta]:
        # NOTE(willkg): We don't have good declared data prior to September
        # 15th, 2025, so don't calculate it if before that date.
        if not self.declared or self.declared <= "2025-09-15" or not self._start_ts:
            return None
        return arrow.get(self.declared) - arrow.get(self._start_ts)

    @property
    def tt_alerted(self) -> Optional[timedelta]:
        # NOTE(willkg): Older incidents had "detected" data and may not
        # have had "alerted" data.
        alerted = self.alerted or self.detected
        if not self._start_ts or not alerted:
            return None
        return arrow.get(alerted) - arrow.get(self._start_ts)

    @property
    def tt_responded(self) -> Optional[timedelta]:
        if not self._start_ts or not self.responded:
            return None
        return arrow.get(self.responded) - arrow.get(self._start_ts)

    @property
    def tt_mitigated(self) -> Optional[timedelta]:
        if not self._start_ts or not self.mitigated:
            return None
        return arrow.get(self.mitigated) - arrow.get(self._start_ts)

    @property
    def tt_resolved(self) -> Optional[timedelta]:
        if not self._start_ts or not self.resolved:
            return None
        return arrow.get(self.resolved) - arrow.get(self._start_ts)

    @property
    def tracked_action_items(self):
        return [item for item in self.action_items or [] if item.url]
