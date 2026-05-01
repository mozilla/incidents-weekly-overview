# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Lists incidents data.
"""

import csv
import dataclasses
import os
import re
import sys
from typing import Optional, Union

import arrow
import click
from dotenv import load_dotenv
import rich

from iim.libgdoc import build_service, update_report
from iim.libjira import JiraAPI, fix_jira_incident_data
from iim.libreport import IncidentReport


load_dotenv()


PERIOD_RE = re.compile(r"^(\d+)(d|w|mo|y)$")

DEFAULT_PERIOD = {
    "working": "14d",
    "resolved": "7d",
    "completed": "7d",
    "not-completed": "6mo",
    "dormant": "6mo",
}

INCIDENT_REPORT_FIELDS = {f.name for f in dataclasses.fields(IncidentReport)}


def parse_output(value: str) -> Union[str, list[str]]:
    """Parse --output value.

    Returns the literal "all" for the rich human-readable view. Otherwise
    treats the value as a comma-separated list of IncidentReport field names
    and returns that list with whitespace stripped. Raises click.BadParameter
    on unknown fields or an empty list.
    """
    if value == "all":
        return "all"
    fields = [f.strip() for f in value.split(",") if f.strip()]
    if not fields:
        raise click.BadParameter(
            "--output must be 'all' or a comma-separated list of fields."
        )
    invalid = [f for f in fields if f not in INCIDENT_REPORT_FIELDS]
    if invalid:
        raise click.BadParameter(
            f"unknown field(s): {', '.join(invalid)}. "
            f"Valid fields: {', '.join(sorted(INCIDENT_REPORT_FIELDS))}"
        )
    return fields


def _format_field(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def parse_period(s: str) -> arrow.Arrow:
    """Parse a duration string (e.g. '7d', '2w', '6mo', '1y') and return the cutoff
    timestamp (now minus the duration)."""
    match = PERIOD_RE.match(s)
    if not match:
        raise click.BadParameter(
            f"Invalid period {s!r}. Use Nd, Nw, Nmo, or Ny (e.g., 7d, 2w, 6mo, 1y)."
        )
    n = int(match.group(1))
    unit = match.group(2)
    now = arrow.now()
    if unit == "d":
        return now.shift(days=-n)
    if unit == "w":
        return now.shift(weeks=-n)
    if unit == "mo":
        return now.shift(months=-n)
    return now.shift(years=-n)


def filter_incidents(
    incidents: list[IncidentReport],
    show: Optional[str],
    period: Optional[str],
) -> tuple[str, list[IncidentReport]]:
    """Filter incidents by --show view.

    Returns (header, selected). When show is None, returns all incidents.
    Raises click.BadParameter if `period` is invalid.
    """
    if show is None:
        return f"All incidents ({len(incidents)})", incidents

    if show == "active":
        selected = [item for item in incidents if item.status != "Resolved"]
        header = f"Active incidents — status is not Resolved ({len(selected)}):"
        return header, selected

    period_str = period or DEFAULT_PERIOD[show]
    cutoff = parse_period(period_str).format("YYYY-MM-DD")

    if show == "working":
        selected = [
            item
            for item in incidents
            if item.status != "Resolved"
            or (item.report_modified and item.report_modified[:10] > cutoff)
        ]
        header = (
            f"Working incidents — unresolved or report touched in last {period_str} "
            f"({len(selected)}):"
        )
        return header, selected

    if show == "resolved":
        selected = [
            item for item in incidents if item.resolved and item.resolved[:10] > cutoff
        ]
        header = f"Resolved incidents — last {period_str} ({len(selected)}):"
        return header, selected

    if show == "completed":
        selected = [
            item
            for item in incidents
            if item.status == "Resolved"
            and item.is_completed
            and item.resolved
            and item.resolved[:10] > cutoff
        ]
        header = (
            f"Completed incidents — resolved and completed in last {period_str} "
            f"({len(selected)}):"
        )
        return header, selected

    if show == "not-completed":
        selected = [
            item
            for item in incidents
            if item.status == "Resolved"
            and not item.is_completed
            and item.resolved
            and item.resolved[:10] > cutoff
        ]
        header = (
            f"Not-completed incidents — resolved but not completed in last "
            f"{period_str} ({len(selected)}):"
        )
        return header, selected

    if show == "dormant":
        selected = [
            item
            for item in incidents
            if item.status != "Resolved"
            and (not item.report_modified or item.report_modified[:10] <= cutoff)
        ]
        header = (
            f"Dormant incidents — unresolved, report not touched in {period_str} "
            f"({len(selected)}):"
        )
        return header, selected

    raise ValueError(f"unknown show value: {show!r}")


@click.command()
@click.option(
    "--show",
    "show",
    type=click.Choice(
        ["working", "resolved", "completed", "not-completed", "active", "dormant"]
    ),
    default=None,
    help=(
        "Filter incidents by view: 'working' (unresolved or report modified within "
        "period), 'resolved' (resolved within period), 'completed' (resolved and "
        "report marked completed within period), 'not-completed' (resolved but "
        "report not marked completed within period), 'active' (status is not "
        "Resolved, no time filter), 'dormant' (unresolved and report not modified "
        "within period). Omit to list all incidents."
    ),
)
@click.option(
    "--period",
    "period",
    default=None,
    help=(
        "Time window as a duration string: Nd (days), Nw (weeks), Nmo (months), "
        "Ny (years). Examples: 7d, 2w, 6mo, 1y. "
        "Defaults: --show working=14d, --show resolved=7d, --show completed=7d, "
        "--show not-completed=6mo, --show dormant=6mo. Ignored when --show=active."
    ),
)
@click.option(
    "--output",
    default="all",
    show_default=True,
    callback=lambda ctx, param, value: parse_output(value),
    help=(
        "Output format. 'all' prints full human-readable details. Otherwise, "
        "a comma-separated list of IncidentReport fields prints one CSV row "
        "per incident with a header row, e.g. 'key,jira_url,report_url'."
    ),
)
@click.option(
    "--client-secret-file",
    default="client_secret.json",
    show_default=True,
    type=click.Path(exists=True),
    help="Path to the OAuth2 client secret JSON file",
)
@click.pass_context
def iim_data(ctx, show, period, output, client_secret_file):
    """
    Lists incidents. Use --show to filter to a specific view.

    See `README.md` for setup instructions.
    """
    if show == "active" and period:
        click.echo("warning: --period is ignored when --show=active", err=True)
    if show is None and period:
        click.echo("warning: --period is ignored when --show is not set", err=True)

    jira = JiraAPI(
        base_url=os.environ["JIRA_URL"].strip(),
        username=os.environ["JIRA_USERNAME"].strip(),
        password=os.environ["JIRA_TOKEN"].strip(),
    )

    needs_drive = (
        output == "all"
        or show in ("working", "dormant")
        or (isinstance(output, list) and "report_modified" in output)
    )
    drive_service = build_service(client_secret_file) if needs_drive else None

    issue_data = jira.get_all_issues_for_project(project_key="IIM")

    incidents = [
        fix_jira_incident_data(jira_url=jira.base_url, incident=incident)
        for incident in issue_data
    ]

    if drive_service:
        incidents = [update_report(drive_service, incident) for incident in incidents]

    header, selected = filter_incidents(incidents, show, period)

    if output == "all":
        click.echo()
        click.echo(f"# {header}")
        click.echo()
        for incident in selected:
            rich.print(
                f"{incident.key}  {incident.severity}  {incident.summary}  "
                f"({incident.entities})"
            )
            rich.print(f"Status:           {incident.status}")
            rich.print(f"Resolved:         {incident.resolved}")
            rich.print(f"Report completed: {incident.is_completed}")
            modified_time = incident.report_modified or "unknown"
            rich.print(f"Doc modified:     {modified_time}")
            click.echo()
            rich.print(f"Jira: {incident.jira_url}")
            rich.print(f"Doc:  {incident.report_url}")
            click.echo()
    else:
        writer = csv.writer(sys.stdout)
        writer.writerow(output)
        for incident in selected:
            writer.writerow([_format_field(getattr(incident, f)) for f in output])
