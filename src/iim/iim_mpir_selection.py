# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Lists service incidents for the monthly incident meeting.
"""

import os

import arrow
import click
from dotenv import load_dotenv

from iim.libjira import JiraAPI, fix_jira_incident_data, generate_jira_link
from iim.libreport import IncidentReport


load_dotenv()


def filter_incidents(incidents: list[IncidentReport], weeks: int):
    """Return incidents declared in the last N weeks with entity_bucket 'service'."""
    start_date = arrow.now().shift(weeks=-weeks).format("YYYY-MM-DD")
    return [
        i
        for i in incidents
        if (
            i.declare_date is not None
            and i.declare_date[:10] >= start_date
            and i.entity_bucket == "service"
        )
    ]


def format_incident_line(incident: IncidentReport) -> str:
    severity = incident.severity or "unknown"
    entities = incident.entities or "unknown"

    if incident.report_url and incident.report_url != "no doc":
        summary_part = f"[{incident.summary}]({incident.report_url})"
    else:
        summary_part = incident.summary

    return (
        f"- [{incident.key}]({incident.jira_url}) "
        f"{incident.status} {severity} {entities} {summary_part}"
    )


def render_report(filtered: list[IncidentReport], weeks: int, jira_url: str) -> str:
    today = arrow.now().format("YYYY-MM-DD")
    start_date = arrow.now().shift(weeks=-weeks).format("YYYY-MM-DD")

    severity_order = {"S1": 0, "S2": 1, "S3": 2, "S4": 3}
    # Stable sort: first by date descending, then by severity ascending
    sorted_incidents = sorted(filtered, key=lambda i: i.declare_date, reverse=True)
    sorted_incidents.sort(key=lambda i: severity_order.get(i.severity, 99))

    lines = ["# Monthly Incident Meeting", ""]

    if not sorted_incidents:
        lines.append(
            f"No service incidents declared in the last {weeks} weeks "
            f"({start_date} to {today})."
        )
        return "\n".join(lines)

    lines.append(
        f"{len(sorted_incidents)} service incidents declared in the last "
        f"{weeks} weeks ({start_date} to {today})."
    )
    lines.append("")

    for incident in sorted_incidents:
        lines.append(format_incident_line(incident))

    lines.append("")
    jira_link = generate_jira_link(
        jira_url=jira_url,
        incident_keys=[i.key for i in sorted_incidents if i.key],
    )
    lines.append(f"[View in Jira]({jira_link})")

    return "\n".join(lines)


@click.command()
@click.option(
    "--weeks",
    default=5,
    show_default=True,
    help="Number of weeks to look back from today.",
)
@click.pass_context
def iim_mpir_selection(ctx, weeks):
    """
    Lists service incidents declared in the last N weeks for the monthly
    incident meeting.

    See `README.md` for setup instructions.
    """
    jira_client = JiraAPI(
        base_url=os.environ["JIRA_URL"].strip(),
        username=os.environ["JIRA_USERNAME"].strip(),
        password=os.environ["JIRA_TOKEN"].strip(),
    )

    click.echo("Fetching incidents...")
    click.echo()

    issue_data = jira_client.get_all_issues_for_project(project_key="IIM")

    incidents = [
        fix_jira_incident_data(jira_url=jira_client.base_url, incident=incident)
        for incident in issue_data
    ]

    filtered = filter_incidents(incidents, weeks)
    output = render_report(filtered, weeks, jira_client.base_url)
    click.echo(output)
