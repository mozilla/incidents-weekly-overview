# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Lists incidents data.
"""

import os
import re

import arrow
import click
from dotenv import load_dotenv
import rich

from iim.libgdoc import build_service, update_report
from iim.libjira import JiraAPI, fix_jira_incident_data


load_dotenv()


PERIOD_RE = re.compile(r"^(\d+)(d|w|mo|y)$")

DEFAULT_PERIOD = {
    "working": "14d",
    "resolved": "7d",
    "dormant": "6mo",
}


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


@click.command()
@click.option(
    "--show",
    "show",
    type=click.Choice(["working", "resolved", "active", "dormant"]),
    default=None,
    help=(
        "Filter incidents by view: 'working' (unresolved or report modified within "
        "period), 'resolved' (resolved within period), 'active' (status is not "
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
        "Defaults: --show working=14d, --show resolved=7d, --show dormant=6mo. "
        "Ignored when --show=active."
    ),
)
@click.option(
    "--output",
    default="all",
    show_default=True,
    type=click.Choice(["all", "report-urls", "jira-urls"]),
    help=(
        "Output format: 'all' prints full details, 'report-urls' prints only the "
        "incident report (Google Doc) URLs, 'jira-urls' prints only the Jira issue URLs."
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

    needs_drive = output == "all" or show in ("working", "dormant")
    drive_service = build_service(client_secret_file) if needs_drive else None

    issue_data = jira.get_all_issues_for_project(project_key="IIM")

    incidents = [
        fix_jira_incident_data(jira_url=jira.base_url, incident=incident)
        for incident in issue_data
    ]

    if drive_service:
        incidents = [update_report(drive_service, incident) for incident in incidents]

    # Header -> list of incidents
    groups = {}

    if show == "working":
        period_str = period or DEFAULT_PERIOD["working"]
        cutoff = parse_period(period_str).format("YYYY-MM-DD")
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
        groups[header] = selected

    elif show == "resolved":
        period_str = period or DEFAULT_PERIOD["resolved"]
        cutoff = parse_period(period_str).format("YYYY-MM-DD")
        selected = [
            item for item in incidents if item.resolved and item.resolved[:10] > cutoff
        ]
        header = f"Resolved incidents — last {period_str} ({len(selected)}):"
        groups[header] = selected

    elif show == "active":
        selected = [item for item in incidents if item.status != "Resolved"]
        header = f"Active incidents — status is not Resolved ({len(selected)}):"
        groups[header] = selected

    elif show == "dormant":
        period_str = period or DEFAULT_PERIOD["dormant"]
        cutoff = parse_period(period_str).format("YYYY-MM-DD")
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
        groups[header] = selected

    else:
        groups[f"All incidents ({len(incidents)})"] = incidents

    for header, incidents_group in groups.items():
        if output == "all":
            click.echo()
            click.echo(f"# {header}")
            click.echo()

        for incident in incidents_group:
            if output == "all":
                rich.print(f"{incident.key}  {incident.summary}  ({incident.entities})")
                rich.print(f"Status:       {incident.status}")
                rich.print(f"Resolved:     {incident.resolved}")
                modified_time = incident.report_modified or "unknown"
                rich.print(f"Doc modified: {modified_time}")
                click.echo()
                rich.print(f"Jira: {incident.jira_url}")
                rich.print(f"Doc:  {incident.report_url}")
                click.echo()

            elif output == "report-urls":
                rich.print(incident.report_url)

            elif output == "jira-urls":
                rich.print(incident.jira_url)
