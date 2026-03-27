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

import arrow
import click
import requests
import rich
from dotenv import load_dotenv

from iim.libgdoc import BadGdocId, build_service, download_gdoc
from iim.libjira import JiraAPI
from iim.libreport import IncidentReport
from iim.libreportparser import parse_markdown


load_dotenv()


ISSUE_KEY_NUM_RE = re.compile(r"[A-Z]+-(\d+)")
JIRA_BROWSE_RE = re.compile(r"/browse/([A-Z]+-\d+)")
GDOC_URL_RE = re.compile(r"docs\.google\.com/document/")


def _issue_key_num(key: str) -> int:
    match = ISSUE_KEY_NUM_RE.search(key or "")
    return int(match.group(1)) if match else 0


def _classify_arg(arg: str) -> tuple[str, str]:
    """Return ('jira_key', key), ('gdoc_url', url), or ('unknown', arg)."""
    if re.match(r"^[A-Z]+-\d+$", arg):
        return "jira_key", arg
    m = JIRA_BROWSE_RE.search(arg)
    if m:
        return "jira_key", m.group(1)
    if GDOC_URL_RE.search(arg):
        return "gdoc_url", arg
    return "unknown", arg


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
        if report.entities is None or not report.entities.strip():
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


class FutureTimestampLintRule(LintRule):
    lr_number = "LR090"
    name = "future-timestamp"
    severity = "err"

    FIELDS = [
        "declare_date",
        "impact_start",
        "declared",
        "detected",
        "alerted",
        "acknowledged",
        "responded",
        "mitigated",
        "resolved",
    ]

    def lint(self, report: IncidentReport) -> Optional[str]:
        now = arrow.now()
        future_fields = [
            field
            for field in self.FIELDS
            if (value := getattr(report, field)) and arrow.get(value) > now
        ]
        if future_fields:
            return f"Fields set to future timestamps: {', '.join(future_fields)}."
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
    FutureTimestampLintRule(),
]


@click.command()
@click.option(
    "--errors-only/--no-errors-only",
    "errors_only",
    default=False,
    help="Only print ERR failures; omit incidents with warnings only",
)
@click.option(
    "--list-rules",
    "list_rules",
    is_flag=True,
    default=False,
    help="List all lint rules and exit",
)
@click.option(
    "--client-secret-file",
    "client_secret_file",
    default="client_secret.json",
    show_default=True,
    help="Google OAuth client secret file (used for Google Doc URLs).",
)
@click.argument("args", nargs=-1)
def iim_lint(
    errors_only: bool,
    list_rules: bool,
    client_secret_file: str,
    args: tuple[str, ...],
):
    """
    Lint IIM incident issues for data quality problems.

    ARGS accepts any mix of:

    \b
    * Jira issue keys, e.g. IIM-131
    * Jira issue URLs, e.g. https://jira.example.net/browse/IIM-131
    * Google Doc URLs, e.g. https://docs.google.com/document/d/...
    """
    if list_rules:
        for rule in LINT_RULES:
            label = rule.severity.upper()
            click.echo(f"[{label} {rule.lr_number} {rule.name}]")
        return

    if not args:
        raise click.UsageError("Provide one or more ARGS.")

    jira_client = JiraAPI(
        base_url=os.environ["JIRA_URL"].strip(),
        username=os.environ["JIRA_USERNAME"].strip(),
        password=os.environ["JIRA_TOKEN"].strip(),
    )

    reports: list[IncidentReport] = []

    drive_service = None
    for arg in args:
        kind, value = _classify_arg(arg)
        if kind == "jira_key":
            try:
                reports.append(jira_client.get_issue_report(value))
            except requests.HTTPError as exc:
                click.echo(f"Error fetching {value}: {exc}. Skipping.")
        elif kind == "gdoc_url":
            try:
                if drive_service is None:
                    drive_service = build_service(client_secret_file)
                _, content = download_gdoc(drive_service, value)
                report = parse_markdown(content)
                if not report.report_url:
                    report.report_url = value
                reports.append(report)
            except BadGdocId as exc:
                click.echo(f"Error fetching {value!r}: {exc}. Skipping.")
        else:
            click.echo(f"Unrecognized input {arg!r}. Skipping.")

    reports.sort(key=lambda r: _issue_key_num(r.key) if r.key else float("inf"))

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
            label = report.key or report.report_url or "(unknown)"
            click.echo(f"{label}: {report.summary}")
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
