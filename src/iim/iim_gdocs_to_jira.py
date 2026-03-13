# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Convert incident reports (as markdown) to field data and push to Jira.
"""

import os
import traceback

import click
from dotenv import load_dotenv
from glom import glom
import rich
from rich.table import Table

from iim.libjira import (
    get_issue_data,
    incident_report_to_jira_field,
    update_jira_issue_data,
    update_jira_issue_status,
)
from iim.libreport import IncidentReport
from iim.libreportparser import NoJiraURLError, NoJiraKeyError, parse_markdown


load_dotenv()


@click.command()
@click.option("--dry-run", default=False, is_flag=True)
@click.argument("docs", nargs=-1)
@click.pass_context
def iim_google_docs_to_jira(ctx: click.Context, dry_run: bool, docs: tuple[str, ...]):
    """
    Prompts user for google doc metadata as markdown. Parses the markdown and
    extracts updated metadata and issue key. Pushes information to Jira.

    Create an API token in Jira and set these in the `.env` file:

    \b
    * JIRA_USERNAME
    * JIRA_TOKEN
    * JIRA_URL
    """
    username = os.environ["JIRA_USERNAME"].strip()
    password = os.environ["JIRA_TOKEN"].strip()
    url = os.environ["JIRA_URL"].strip().rstrip("/")

    if not docs:
        raise click.BadParameter(
            "Requires at least one doc",
            ctx=ctx,
            param_hint="docs",
        )

    for fn in sorted(docs):
        click.echo()
        with open(fn, "r") as fp:
            md_data = fp.read()
            lines = md_data.strip().splitlines()
            for line in lines:
                if line.startswith("# Incident"):
                    break
            else:
                click.echo(f"{fn} is not an incident report. Skipping.")
                continue

            click.echo(f"Parsing {fn}...")

            try:
                markdown_report: IncidentReport = parse_markdown(md_data)
            except (KeyError, IndexError):
                traceback.print_exc()
                click.echo("Error parsing document.")
                click.echo("Next?")
                user_input = input()
                continue
            except (NoJiraKeyError, NoJiraURLError):
                traceback.print_exc()
                click.echo("This incident report doesn't have the Jira IIM key.")
                click.echo("Next?")
                user_input = input()

            jira_incident: IncidentReport = get_issue_data(
                jira_base_url=url,
                username=username,
                password=password,
                issue_key=markdown_report.key,
            )

            updated_fields = {}

            # Update summary
            # NOTE(willkg): before 20260312, the source for declare date was
            # the jira incident issue. after that, we pull it from the incident
            # report field
            summary = markdown_report.summary
            declare_date = markdown_report.declare_date or jira_incident.declare_date
            if declare_date:
                summary = f"{summary} ({declare_date})"
            updated_fields["summary"] = summary.strip()

            # NOTE(willkg): if the update is to set this field to None, then set it
            # to whatever Jira has already
            updated_fields["customfield_15087"] = (
                markdown_report.declare_date or jira_incident.declare_date
            )
            updated_fields["customfield_18692"] = (
                markdown_report.declared or jira_incident.declared
            )

            # These are options, so we have to set the value value
            if markdown_report.severity:
                updated_fields["customfield_10319"] = {
                    "value": markdown_report.severity
                }
            else:
                updated_fields["customfield_10319"] = None
            if markdown_report.detection_method:
                updated_fields["customfield_12881"] = {
                    "value": markdown_report.detection_method
                }
            else:
                updated_fields["customfield_12881"] = None
            # These are more straightforward
            updated_fields["customfield_18693"] = markdown_report.impact_start
            updated_fields["customfield_18694"] = markdown_report.detected
            updated_fields["customfield_18695"] = markdown_report.alerted
            updated_fields["customfield_18696"] = markdown_report.acknowledged
            updated_fields["customfield_18697"] = markdown_report.responded
            updated_fields["customfield_18698"] = markdown_report.mitigated
            updated_fields["customfield_18699"] = markdown_report.resolved

            # TODO: Update services
            # TODO: Update post-mortem actions -- not in metadata

            click.echo()
            click.echo("Data to update:")
            click.echo(f"Jira: {markdown_report.jira_url}")
            click.echo(f"Incident Report: {jira_incident.report_url}")

            changes = False

            table = Table()
            table.add_column("field")
            table.add_column("current")
            table.add_column("new")

            # NOTE(willkg): status gets updated separately, but we want to show
            # it in the table, so we do this
            current_value = jira_incident.status
            new_value = markdown_report.status
            if current_value != new_value:
                current_value = f"[yellow]{current_value}[/yellow]"
                new_value = f"[yellow]{new_value}[/yellow]"
                changes = True
                table.add_row("status", current_value, new_value)

            for name, field in (
                ("summary", "summary"),
                ("severity", "severity"),
                ("detection method", "detection_method"),
                ("declare date", "declare_date"),
                ("impact start (ts)", "impact_start"),
                ("time declared (ts)", "declared"),
                ("time detected (ts)", "detected"),
                ("time alerted (ts)", "alerted"),
                ("time acknowledged (ts)", "acknowledged"),
                ("time responded (ts)", "responded"),
                ("time mitigated (ts)", "mitigated"),
                ("time resolved (ts)", "resolved"),
            ):
                current_value = str(getattr(jira_incident, field))
                new_value = str(
                    glom(updated_fields, incident_report_to_jira_field(field))
                )

                if current_value != new_value:
                    current_value = f"[yellow]{current_value}[/yellow]"
                    new_value = f"[yellow]{new_value}[/yellow]"
                    changes = True
                table.add_row(name, current_value, new_value)

            rich.print(table)
            click.echo()

            if not changes:
                click.echo("Nothing to change.")
                click.echo("Next?")
                user_input = input()

            elif dry_run:
                click.echo("Dry-run mode. Pass without --dry-run to commit.")
                click.echo("Next?")
                user_input = input()

            else:
                click.echo("ENTER to commit, CTRL-C to exit, S to skip")
                user_input = input()
                if user_input.strip().lower() == "s":
                    continue

                click.echo("Committing to Jira ...")
                if jira_incident.status != markdown_report.status:
                    update_jira_issue_status(
                        jira_base_url=url,
                        username=username,
                        password=password,
                        issue_key=markdown_report.key,
                        new_status=markdown_report.status,
                    )
                update_jira_issue_data(
                    jira_base_url=url,
                    username=username,
                    password=password,
                    issue_key=markdown_report.key,
                    updated_fields=updated_fields,
                )

    click.echo("Done!")
