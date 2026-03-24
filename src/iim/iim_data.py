# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Lists incidents data.
"""

import os

import arrow
import click
from dotenv import load_dotenv
import rich

from iim.libgdoc import build_service, update_report
from iim.libjira import JiraAPI, fix_jira_incident_data


load_dotenv()


@click.command()
@click.option(
    "--active-only/--no-active-only",
    default=False,
    show_default=True,
    help=(
        "Whether or not to show active incidents, recently resolved incidents, and "
        "incidents where the report has been updated recently."
    ),
)
@click.option(
    "--details/--no-details",
    default=True,
    show_default=True,
    help="Whether or not to print all the details or just incident report urls.",
)
@click.option(
    "--client-secret-file",
    default="client_secret.json",
    show_default=True,
    type=click.Path(exists=True),
    help="Path to the OAuth2 client secret JSON file",
)
@click.pass_context
def iim_data(ctx, active_only, details, client_secret_file):
    """
    Lists all incidents. Can also list active incidents.

    Create an API token in Jira and set these in the `.env` file:

    \b
    * JIRA_USERNAME
    * JIRA_TOKEN
    * JIRA_URL
    """
    jira = JiraAPI(
        base_url=os.environ["JIRA_URL"].strip(),
        username=os.environ["JIRA_USERNAME"].strip(),
        password=os.environ["JIRA_TOKEN"].strip(),
    )

    drive_service = None
    if details or active_only:
        drive_service = build_service(client_secret_file)

    issue_data = jira.get_all_issues_for_project(project_key="IIM")

    incidents = [
        fix_jira_incident_data(jira_url=jira.base_url, incident=incident)
        for incident in issue_data
    ]

    if drive_service:
        incidents = [update_report(drive_service, incident) for incident in incidents]

    def print_incident(incident, details):
        if details:
            rich.print(f"{incident.key}  {incident.summary}  ({incident.entities})")
            rich.print(f"Status:       {incident.status}")
            rich.print(f"Resolved:     {incident.resolved}")
            modified_time = incident.report_modified or "unknown"
            rich.print(f"Doc modified: {modified_time}")
            click.echo()
            rich.print(f"Jira: {incident.jira_url}")
            rich.print(f"Doc:  {incident.report_url}")
            click.echo()
        else:
            rich.print(incident.report_url)

    # Header -> list of incidents
    groups = {}

    if active_only:
        two_weeks_ago = arrow.now().shift(days=-14).format("YYYY-MM-DD")

        resolved_incidents = [
            item
            for item in incidents
            if item.resolved and item.resolved > two_weeks_ago
        ]
        header = f"Recently resolved incidents ({len(resolved_incidents)}):"
        groups[header] = resolved_incidents

        active_incidents = [item for item in incidents if item.status != "Resolved"]
        header = f"Active incidents ({len(active_incidents)}):"
        groups[header] = active_incidents

        shown_keys = {i.key for i in resolved_incidents} | {
            i.key for i in active_incidents
        }
        recently_updated = [
            item
            for item in incidents
            if item.key not in shown_keys
            and item.report_modified
            and item.report_modified > two_weeks_ago
        ]
        header = f"Recently updated docs ({len(recently_updated)}):"
        groups[header] = recently_updated

    else:
        groups[f"All incidents ({len(incidents)})"] = incidents

    for header, incidents_group in groups.items():
        if details:
            click.echo()
            click.echo(f"# {header}")
            click.echo()
        for incident in incidents_group:
            print_incident(incident=incident, details=details)
