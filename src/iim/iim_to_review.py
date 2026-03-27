# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Lists resolved incidents that have not been marked as completed.
"""

import os

import arrow
import click
from dotenv import load_dotenv

from iim.libjira import JiraAPI, fix_jira_incident_data
from iim.libstats import humanize_timedelta


load_dotenv()


def filter_incidents(incidents):
    """Return (resolved_in_window, to_review) where both are filtered to the
    last 3 months. to_review excludes completed incidents."""
    cutoff = arrow.now().shift(months=-3)
    resolved_in_window = [
        i
        for i in incidents
        if i.status == "Resolved" and i.resolved and arrow.get(i.resolved) >= cutoff
    ]
    to_review = [i for i in resolved_in_window if not i.is_completed]
    return resolved_in_window, to_review


def render_report(resolved_in_window, to_review):
    n = len(resolved_in_window)
    m = len(to_review)

    lines = []
    lines.append("# Incidents to Review")
    lines.append("")

    if m == 0:
        lines.append(
            f"All {n} resolved incidents in the last 3 months have been completed."
        )
        return "\n".join(lines)

    lines.append(f"{m} of {n} resolved incidents in the last 3 months are incomplete.")

    sorted_incidents = sorted(
        to_review,
        key=lambda i: i.resolved or "",
        reverse=True,
    )

    for incident in sorted_incidents:
        lines.append("")
        lines.append(f"## {incident.key}: {incident.summary}")
        lines.append("")

        severity = incident.severity or "unknown"
        lines.append(f"- **Severity:** {severity}")

        if incident.resolved:
            ago = humanize_timedelta(arrow.now() - arrow.get(incident.resolved))
            lines.append(f"- **Resolved:** {incident.resolved} ({ago} ago)")
        else:
            lines.append("- **Resolved:** unknown (unknown ago)")

        lines.append(f"- **Jira:** [{incident.key}]({incident.jira_url})")

        if incident.report_url and incident.report_url != "no doc":
            lines.append(f"- **Report:** [incident report]({incident.report_url})")
        else:
            lines.append("- **Report:** no report")

    return "\n".join(lines)


@click.command()
def iim_to_review():
    """
    Lists resolved incidents that have not been marked as completed.
    """
    jira = JiraAPI(
        base_url=os.environ["JIRA_URL"].strip(),
        username=os.environ["JIRA_USERNAME"].strip(),
        password=os.environ["JIRA_TOKEN"].strip(),
    )

    click.echo("Fetching incidents...")
    click.echo()

    issue_data = jira.get_all_issues_for_project(project_key="IIM")
    incidents = [
        fix_jira_incident_data(jira_url=jira.base_url, incident=issue)
        for issue in issue_data
    ]

    resolved_in_window, to_review = filter_incidents(incidents)
    click.echo(render_report(resolved_in_window, to_review))
