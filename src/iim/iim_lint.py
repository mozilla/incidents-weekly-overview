# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Lint Jira incident issues for data quality problems.

Fetches one or more IIM incidents from Jira, runs each through a set of lint
rules, and prints a report of any failures.
"""

import os
import re
import sys
from typing import Optional

import click
import requests
import rich
from dotenv import load_dotenv

from iim.libjira import JiraAPI, fix_jira_incident_data
from iim.libreport import IncidentReport


load_dotenv()


ISSUE_KEY_NUM_RE = re.compile(r"[A-Z]+-(\d+)")


def _issue_key_num(key: str) -> int:
    match = ISSUE_KEY_NUM_RE.search(key or "")
    return int(match.group(1)) if match else 0


class LintRule:
    lr_number: str
    name: str
    severity: str  # "err" or "warn"

    def lint(self, report: IncidentReport) -> Optional[str]:
        raise NotImplementedError


class MissingResolvedLintRule(LintRule):
    lr_number = "LR010"
    name = "missing-resolved"
    severity = "err"

    def lint(self, report: IncidentReport) -> Optional[str]:
        if report.status == "Resolved" and not report.resolved:
            return 'Status is "Resolved" but resolved timestamp is not set.'
        return None


class MissingMitigatedLintRule(LintRule):
    lr_number = "LR020"
    name = "missing-mitigated"
    severity = "err"

    def lint(self, report: IncidentReport) -> Optional[str]:
        if report.status == "Mitigated" and not report.mitigated:
            return 'Status is "Mitigated" but mitigated timestamp is not set.'
        return None


class WrongStatusLintRule(LintRule):
    lr_number = "LR030"
    name = "wrong-status"
    severity = "err"

    def lint(self, report: IncidentReport) -> Optional[str]:
        messages = []
        if report.resolved and report.status != "Resolved":
            messages.append(f'Has resolved timestamp but status is "{report.status}".')
        if report.mitigated and report.status not in ("Mitigated", "Resolved"):
            messages.append(f'Has mitigated timestamp but status is "{report.status}".')
        return " ".join(messages) if messages else None


class MissingEntitiesLintRule(LintRule):
    lr_number = "LR040"
    name = "missing-entities"
    severity = "err"

    def lint(self, report: IncidentReport) -> Optional[str]:
        if not report.entities or report.entities == "unknown":
            return "Entities is not set."
        return None


class MissingDatesLintRule(LintRule):
    lr_number = "LR050"
    name = "missing-dates"
    severity = "err"

    def lint(self, report: IncidentReport) -> Optional[str]:
        messages = []
        if not report.declare_date:
            messages.append("declare_date is not set.")
        if not report.declared:
            messages.append("declared is not set.")
        return " ".join(messages) if messages else None


class MismatchedDeclareDateLintRule(LintRule):
    lr_number = "LR060"
    name = "mismatched-declare-date"
    severity = "err"

    def lint(self, report: IncidentReport) -> Optional[str]:
        if not report.declare_date or not report.declared:
            return None
        if report.declared[:10] != report.declare_date:
            return (
                f"declare_date {report.declare_date!r} does not match "
                f"date portion of declared {report.declared[:10]!r}."
            )
        return None


class MissingActionItemsLintRule(LintRule):
    lr_number = "LR070"
    name = "missing-action-items"
    severity = "warn"

    def lint(self, report: IncidentReport) -> Optional[str]:
        if report.status == "Resolved" and not report.action_items:
            return 'Status is "Resolved" but there are no action items.'
        return None


class UndeterminedSeverityLintRule(LintRule):
    lr_number = "LR080"
    name = "undetermined-severity"
    severity = "warn"

    def lint(self, report: IncidentReport) -> Optional[str]:
        if report.severity == "undetermined":
            return 'Severity is "undetermined".'
        return None


LINT_RULES: list[LintRule] = [
    MissingResolvedLintRule(),
    MissingMitigatedLintRule(),
    WrongStatusLintRule(),
    MissingEntitiesLintRule(),
    MissingDatesLintRule(),
    MismatchedDeclareDateLintRule(),
    MissingActionItemsLintRule(),
    UndeterminedSeverityLintRule(),
]


@click.command()
@click.option(
    "--all",
    "fetch_all",
    is_flag=True,
    default=False,
    help="Fetch all IIM incident issues instead of specific keys",
)
@click.option(
    "--errors-only/--no-errors-only",
    "errors_only",
    default=False,
    help="Only print ERR failures; omit incidents with warnings only",
)
@click.argument("issue_keys", nargs=-1)
def iim_lint(fetch_all: bool, errors_only: bool, issue_keys: tuple[str, ...]):
    """
    Lint Jira IIM incident issues for data quality problems.

    ISSUE_KEYS are bare Jira issue keys, e.g. IIM-131.

    Either provide ISSUE_KEYS or use --all to fetch every incident.
    """
    if fetch_all and issue_keys:
        raise click.UsageError("Provide either ISSUE_KEYS or --all, not both.")
    if not fetch_all and not issue_keys:
        raise click.UsageError("Provide one or more ISSUE_KEYS or use --all.")

    jira_client = JiraAPI(
        base_url=os.environ["JIRA_URL"].strip(),
        username=os.environ["JIRA_USERNAME"].strip(),
        password=os.environ["JIRA_TOKEN"].strip(),
    )
    jira_url = os.environ["JIRA_URL"].strip()

    reports: list[IncidentReport] = []

    if fetch_all:
        raw_issues = jira_client.get_all_issues_for_project("IIM")
        click.echo(f"Fetching {len(raw_issues)} incidents...")
        for issue in raw_issues:
            remotelinks = jira_client.get_issue_remotelinks(issue["key"])
            reports.append(
                fix_jira_incident_data(
                    jira_url=jira_url,
                    incident=issue,
                    remotelinks=remotelinks,
                )
            )
    else:
        for key in issue_keys:
            try:
                reports.append(jira_client.get_issue_report(key))
            except requests.HTTPError as exc:
                click.echo(f"Error fetching {key}: {exc}. Skipping.")

    reports.sort(key=lambda r: _issue_key_num(r.key))

    failure_count = 0
    for report in reports:
        failures = []
        for rule in LINT_RULES:
            msg = rule.lint(report)
            if msg:
                failures.append((rule, msg))

        if failures:
            printable = (
                [(rule, msg) for rule, msg in failures if rule.severity == "err"]
                if errors_only
                else failures
            )
            if not printable:
                continue
            failure_count += 1
            click.echo(f"{report.key}: {report.summary}")
            click.echo(f"  jira: {report.jira_url}")
            click.echo(f"  report: {report.report_url}")
            for rule, msg in printable:
                label = rule.severity.upper()
                prefix = f"[{label} {rule.lr_number} {rule.name}]"
                if rule.severity == "err":
                    rich.print(f"  [bright_red]{prefix} {msg}[/bright_red]")
                else:
                    rich.print(f"  [bright_yellow]{prefix} {msg}[/bright_yellow]")

    click.echo(f"Checked {len(reports)} incidents. {failure_count} had lint failures.")

    if failure_count:
        sys.exit(1)
