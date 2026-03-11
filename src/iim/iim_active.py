# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Computes a list of recently resolved incidents and a list of active incidents
based on Jira data from `iim_data.py`.
"""

import os

import arrow
import click
from dotenv import load_dotenv
import rich

from iim.libjira import (
    fix_incident_data,
    get_all_issues_for_project,
)


DATADIR = "iim_data"


load_dotenv()


@click.command()
@click.option(
    "--details/--no-details",
    default="True",
    show_default=True,
    help="Whether or not to print all the details or just the urls.",
)
@click.pass_context
def iim_active(ctx, details):
    """
    Computes a list of recently resolved incidents and a list of active
    incidents from Jira incident data.

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
        fix_incident_data(jira_url=url, incident=incident) for incident in issue_data
    ]

    # shift to last week, floor('week') gets monday, shift 4 days to friday
    two_weeks_ago = arrow.now().shift(days=-14).format("YYYY-MM-DD")

    resolved_incidents = [
        item
        for item in incidents
        if item["resolved"] and item["resolved"] > two_weeks_ago
    ]
    if details:
        click.echo()
        click.echo(f"# Recently resolved incidents ({len(resolved_incidents)}):")
        click.echo()
    for incident in resolved_incidents:
        if details:
            rich.print(
                f"{incident['key']}  {incident['summary']}  ({incident['entities']})"
            )
            rich.print(incident["resolved"])
            rich.print(incident["jira_url"])
        rich.print(incident["report_url"])
        if details:
            click.echo()

    active_incidents = [item for item in incidents if item["status"] != "Resolved"]
    if details:
        click.echo()
        click.echo(f"# Active incidents ({len(active_incidents)}):")
        click.echo()
    for incident in active_incidents:
        if details:
            rich.print(
                f"{incident['key']}  {incident['summary']}  ({incident['entities']})"
            )
            rich.print(incident["jira_url"])
        rich.print(incident["report_url"])
        if details:
            click.echo()
