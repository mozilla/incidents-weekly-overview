# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Convert incident reports (as markdown) to field data and push to Jira.
"""

from dataclasses import dataclass
import os
import traceback
from typing import Any

import click
from dotenv import load_dotenv
import rich
from rich.table import Table

from iim.libjira import (
    get_issue_report,
    to_jira_field,
    update_jira_issue_data,
    update_jira_issue_status,
    add_jira_issue_link,
    add_remote_link,
    remove_jira_issue_link,
    remove_remote_link,
)
from iim.libreport import (
    IncidentReport,
    jira_key,
)
from iim.libreportparser import NoJiraIIMURLError, NoJiraIIMKeyError, parse_markdown


load_dotenv()


class InvalidIncidentReport(Exception):
    pass


def read_markdown(fn: str) -> str:
    with open(fn, "r") as fp:
        md_data = fp.read()

    lines = md_data.strip().splitlines()
    for line in lines:
        if line.startswith("# Incident:"):
            break
    else:
        raise InvalidIncidentReport(f"{fn} is not an incident report")
    return md_data


@dataclass
class Diff:
    name: str
    old_value: Any
    new_value: Any
    field_value: Any


def generate_status_diff(jira_data, report_data):
    return Diff(
        name="status",
        old_value=jira_data.status,
        new_value=report_data.status,
        field_value=None,
    )


def generate_metadata_diff(jira_data, report_data):
    diff = []

    # Update summary
    # NOTE(willkg): before 20260312, the source for declare date was
    # the jira incident issue. after that, we pull it from the incident
    # report field
    summary = report_data.summary or "unknown"
    declare_date = report_data.declare_date or jira_data.declare_date
    if declare_date and not summary.endswith(f" ({declare_date})"):
        summary = f"{summary} ({declare_date})"
    diff.append(
        Diff(
            name="summary",
            old_value=jira_data.summary,
            new_value=summary.strip(),
            field_value={to_jira_field("summary"): summary.strip()},
        )
    )

    # NOTE(willkg): if the update is to set this field to None, then set it
    # to whatever Jira has already
    diff.append(
        Diff(
            name="declare date",
            old_value=jira_data.declare_date,
            new_value=report_data.declare_date or jira_data.declare_date,
            field_value={
                to_jira_field("declare_date"): report_data.declare_date
                or jira_data.declare_date
            },
        )
    )
    diff.append(
        Diff(
            name="time declared (ts)",
            old_value=jira_data.declared,
            new_value=report_data.declared or jira_data.declared,
            field_value={
                to_jira_field("declared"): report_data.declared or jira_data.declared
            },
        )
    )

    # These are options, so we have to set the value value
    diff.append(
        Diff(
            name="severity",
            old_value=jira_data.severity,
            new_value=report_data.severity,
            field_value={
                to_jira_field("severity"): {"value": report_data.severity}
                if report_data.severity
                else None
            },
        )
    )
    diff.append(
        Diff(
            name="detection_method",
            old_value=jira_data.detection_method,
            new_value=report_data.detection_method,
            field_value={
                to_jira_field("detection_method"): {
                    "value": report_data.detection_method
                }
                if report_data.detection_method
                else None
            },
        )
    )
    # These are more straightforward
    diff.append(
        Diff(
            name="impact start (ts)",
            old_value=jira_data.impact_start,
            new_value=report_data.impact_start,
            field_value={to_jira_field("impact_start"): report_data.impact_start},
        )
    )
    # NOTE(willkg): we dropped detected
    diff.append(
        Diff(
            name="alerted (ts)",
            old_value=jira_data.alerted,
            new_value=report_data.alerted,
            field_value={to_jira_field("alerted"): report_data.alerted},
        )
    )
    diff.append(
        Diff(
            name="acknowledged (ts)",
            old_value=jira_data.acknowledged,
            new_value=report_data.acknowledged,
            field_value={to_jira_field("acknowledged"): report_data.acknowledged},
        )
    )
    diff.append(
        Diff(
            name="responded (ts)",
            old_value=jira_data.responded,
            new_value=report_data.responded,
            field_value={to_jira_field("responded"): report_data.responded},
        )
    )
    diff.append(
        Diff(
            name="mitigated (ts)",
            old_value=jira_data.mitigated,
            new_value=report_data.mitigated,
            field_value={to_jira_field("mitigated"): report_data.mitigated},
        )
    )
    diff.append(
        Diff(
            name="resolved (ts)",
            old_value=jira_data.resolved,
            new_value=report_data.resolved,
            field_value={to_jira_field("resolved"): report_data.resolved},
        )
    )
    return diff


def generate_actions_diff(jira_data, report_data):
    diff = []

    all_action_items = set()

    # url -> item
    jira_action_items = {}
    for item in jira_data.action_items or []:
        if not item.url:
            continue
        all_action_items.add(item.url)
        jira_action_items[item.url] = item

    # url -> item
    markdown_report_action_items = {}
    for item in report_data.action_items or []:
        if not item.url:
            continue
        all_action_items.add(item.url)
        markdown_report_action_items[item.url] = item

    for item_url in all_action_items:
        current_action_item = jira_action_items.get(item_url)
        current_value = current_action_item.essence() if current_action_item else None

        new_action_item = markdown_report_action_items.get(item_url)
        new_value = new_action_item.essence() if new_action_item else None

        diff.append(
            Diff(
                name="action item",
                old_value=current_value,
                new_value=new_value,
                field_value=[current_action_item, new_action_item],
            )
        )
    return diff


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
    jira_url = os.environ["JIRA_URL"].strip().rstrip("/")

    if not docs:
        raise click.BadParameter(
            "Requires at least one doc",
            ctx=ctx,
            param_hint="docs",
        )

    for fn in sorted(docs):
        click.echo(f"Working on {fn}...")
        try:
            md_data = read_markdown(fn)
        except InvalidIncidentReport as exc:
            click.echo(f"Error: {exc}. Skipping")
            continue

        try:
            markdown_report: IncidentReport = parse_markdown(md_data)
        except (KeyError, IndexError):
            traceback.print_exc()
            click.echo("Error: Error parsing document.")
            click.echo("Next?")
            user_input = input()
            continue
        except (NoJiraIIMKeyError, NoJiraIIMURLError):
            click.echo("Error: This incident report doesn't have the Jira IIM key.")
            click.echo("Next?")
            user_input = input()
            continue

        jira_incident: IncidentReport = get_issue_report(
            jira_base_url=jira_url,
            username=username,
            password=password,
            issue_key=markdown_report.key,
        )

        # Generate an understanding of what changed
        status_diff = generate_status_diff(
            jira_data=jira_incident, report_data=markdown_report
        )
        metadata_diff = generate_metadata_diff(
            jira_data=jira_incident, report_data=markdown_report
        )
        actions_diff = generate_actions_diff(
            jira_data=jira_incident, report_data=markdown_report
        )

        # TODO: Update services
        # TODO: Update post-mortem actions -- not in metadata

        # Print out a summary of everything and denote what changed
        click.echo()
        click.echo("Data to update:")
        click.echo(f"Jira: {markdown_report.jira_url}")
        click.echo(f"Incident Report: {jira_incident.report_url}")

        changes = False

        table = Table()
        table.add_column("field")
        table.add_column("current")
        table.add_column("new")

        all_diffs = [status_diff] + metadata_diff + actions_diff

        for part in all_diffs:
            old_value = str(part.old_value)
            new_value = str(part.new_value)
            if old_value != new_value:
                old_value = f"[yellow]{old_value}[/yellow]"
                new_value = f"[yellow]{new_value}[/yellow]"
                changes = True
            table.add_row(part.name, old_value, new_value)

        rich.print(table)

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

            # Handle status transition changes
            if status_diff.old_value != status_diff.new_value:
                update_jira_issue_status(
                    jira_base_url=jira_url,
                    username=username,
                    password=password,
                    issue_key=markdown_report.key,
                    new_status=status_diff.new_value,
                )

            # Update metadata
            updated_fields = {}
            for item in metadata_diff:
                updated_fields.update(item.field_value)
            update_jira_issue_data(
                jira_base_url=jira_url,
                username=username,
                password=password,
                issue_key=markdown_report.key,
                updated_fields=updated_fields,
            )

            for item in actions_diff:
                if item.new_value and not item.old_value:
                    # Item needs to be added
                    linked_key = jira_key(item.field_value[1].url)
                    if linked_key:
                        add_jira_issue_link(
                            jira_base_url=jira_url,
                            username=username,
                            password=password,
                            incident_key=markdown_report.key,
                            linked_issue_key=linked_key,
                        )
                    else:
                        add_remote_link(
                            jira_base_url=jira_url,
                            username=username,
                            password=password,
                            incident_key=markdown_report.key,
                            action_item=item.field_value[1],
                        )
                elif item.old_value and not item.new_value:
                    # Item needs to be removed
                    linked_key = jira_key(item.field_value[0].url)
                    if linked_key:
                        remove_jira_issue_link(
                            jira_base_url=jira_url,
                            username=username,
                            password=password,
                            link_id=item.field_value[0].jira_id,
                        )
                    else:
                        remove_remote_link(
                            jira_base_url=jira_url,
                            username=username,
                            password=password,
                            incident_key=markdown_report.key,
                            action_item=item.field_value[0],
                        )
                else:
                    # Item needs to be updated--old one removed and new one
                    # added
                    remove_remote_link(
                        jira_base_url=jira_url,
                        username=username,
                        password=password,
                        incident_key=markdown_report.key,
                        action_item=item.field_value[0],
                    )
                    add_remote_link(
                        jira_base_url=jira_url,
                        username=username,
                        password=password,
                        incident_key=markdown_report.key,
                        action_item=item.field_value[1],
                    )

    click.echo("Done!")
