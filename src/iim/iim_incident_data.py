# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Downloads Jira data for an IIM incident and outputs it as JSON.
"""

import dataclasses
import json
import os

import click
from dotenv import load_dotenv

from iim.libgdoc import build_service, update_report
from iim.libjira import JiraAPI


load_dotenv()


@click.command()
@click.argument("issue_key")
@click.option(
    "--client-secret-file",
    default="client_secret.json",
    show_default=True,
    type=click.Path(exists=True),
    help="Path to the OAuth2 client secret JSON file",
)
def iim_incident_data(issue_key, client_secret_file):
    """Download Jira data for ISSUE_KEY (e.g. IIM-141) and output as JSON."""
    jira = JiraAPI(
        base_url=os.environ["JIRA_URL"].strip(),
        username=os.environ["JIRA_USERNAME"].strip(),
        password=os.environ["JIRA_TOKEN"].strip(),
    )

    drive_service = build_service(client_secret_file)
    report = jira.get_issue_report(issue_key)
    update_report(drive_service, report)

    def fmt_td(td):
        return str(td) if td is not None else None

    data = dataclasses.asdict(report)
    # Include computed properties that dataclasses.asdict() skips
    data["entity_bucket"] = report.entity_bucket
    data["is_completed"] = report.is_completed
    data["age"] = fmt_td(report.age)
    data["tt_declared"] = fmt_td(report.tt_declared)
    data["tt_alerted"] = fmt_td(report.tt_alerted)
    data["tt_responded"] = fmt_td(report.tt_responded)
    data["tt_mitigated"] = fmt_td(report.tt_mitigated)
    data["tt_resolved"] = fmt_td(report.tt_resolved)
    click.echo(json.dumps(data, indent=2))
