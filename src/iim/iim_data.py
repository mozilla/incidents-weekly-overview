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

from iim.libjira import (
    fix_jira_incident_data,
    get_all_issues_for_project,
)


load_dotenv()


@click.command()
@click.option(
    "--active/--no-active",
    default="False",
    show_default=True,
    help="Whether or not to show active incidents.",
)
@click.option(
    "--details/--no-details",
    default="True",
    show_default=True,
    help="Whether or not to print all the details or just incident report urls.",
)
@click.pass_context
def iim_data(ctx, active, details):
    """
    Lists all incidents. Can also list active incidents.

    Create an API token in Jira and set these in the `.env` file:

    \b
    * JIRA_USERNAME
    * JIRA_TOKEN
    * JIRA_URL
    """
    username = os.environ["JIRA_USERNAME"].strip()
    password = os.environ["JIRA_TOKEN"].strip()
    url = os.environ["JIRA_URL"].strip().rstrip("/")

    issue_data = get_all_issues_for_project(
        jira_base_url=url,
        project_key="IIM",
        username=username,
        password=password,
    )

    incidents = [
        fix_jira_incident_data(jira_url=url, incident=incident)
        for incident in issue_data
    ]

    def print_incident(incident, details):
        if details:
            rich.print(
                f"{incident['key']}  {incident['summary']}  ({incident['entities']})"
            )
            rich.print(incident["resolved"])
            rich.print(incident["jira_url"])
        rich.print(incident["report_url"])
        if details:
            click.echo()

    # Header -> list of incidents
    groups = {}

    if active:
        # shift to last week, floor('week') gets monday, shift 4 days to friday
        two_weeks_ago = arrow.now().shift(days=-14).format("YYYY-MM-DD")

        resolved_incidents = [
            item
            for item in incidents
            if item["resolved"] and item["resolved"] > two_weeks_ago
        ]
        header = f"Recently resolved incidents ({len(resolved_incidents)}):"
        groups[header] = resolved_incidents

        active_incidents = [item for item in incidents if item["status"] != "Resolved"]
        header = f"Active incidents ({len(active_incidents)}):"
        groups[header] = active_incidents

    else:
        groups[f"All incidents ({len(incidents)})"] = incidents

    for header, incidents_group in groups.items():
        if details:
            click.echo()
            click.echo(f"# {header}")
            click.echo()
        for incident in incidents_group:
            print_incident(incident=incident, details=details)
