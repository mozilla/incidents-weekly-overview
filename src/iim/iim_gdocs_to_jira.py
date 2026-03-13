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
    extract_doc,
    get_issue_data,
    update_jira_issue_data,
    update_jira_issue_status,
)
from iim.libreportparser import NoJiraKeyError, parse_markdown


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
                new_data = parse_markdown(md_data)
            except (KeyError, IndexError):
                traceback.print_exc()
                click.echo("Error parsing document.")
                click.echo("Next?")
                user_input = input()
                continue
            except NoJiraKeyError:
                traceback.print_exc()
                click.echo("This incident report doesn't have the Jira IIM key.")
                click.echo("Next?")
                user_input = input()

            incident_key = new_data["key"]

            incident = get_issue_data(
                jira_base_url=url,
                username=username,
                password=password,
                issue_key=incident_key,
            )

            updated_fields = {}

            # Update summary
            updated_fields["summary"] = new_data["summary"]
            if incident["fields"]["customfield_15087"]:
                updated_fields["summary"] = (
                    updated_fields["summary"]
                    + f" ({incident['fields']['customfield_15087']})"
                )
            updated_fields["summary"] = updated_fields["summary"].strip()
            updated_fields["customfield_10319"] = new_data["severity"]
            updated_fields["customfield_12881"] = new_data["detection method"]
            updated_fields["customfield_18693"] = new_data["impact start"]
            updated_fields["customfield_18694"] = new_data["detected"]
            updated_fields["customfield_18695"] = new_data["alerted"]
            updated_fields["customfield_18696"] = new_data["acknowledged"]
            updated_fields["customfield_18697"] = new_data["responded"]
            updated_fields["customfield_18698"] = new_data["mitigated"]
            updated_fields["customfield_18699"] = new_data["resolved"]

            # Don't update these if the update is to set them to None
            if new_data["declare date"]:
                updated_fields["customfield_15087"] = new_data["declare date"]
            else:
                updated_fields["customfield_15087"] = glom(
                    incident, "fields.customfield_15087"
                )
            if new_data["declared"]:
                updated_fields["customfield_18692"] = new_data["declared"]
            else:
                updated_fields["customfield_18692"] = glom(
                    incident, "fields.customfield_18692"
                )

            # TODO: Update services
            # TODO: Update post-mortem actions -- not in metadata

            click.echo()
            click.echo("Data to update:")
            click.echo(f"Jira:{url}/browse/{incident['key']}")
            click.echo(f"Incident Report: {extract_doc(incident)}")
            click.echo("Status: " + incident["fields"]["status"]["name"])

            changes = False

            table = Table()
            table.add_column("field")
            table.add_column("current")
            table.add_column("new")

            table.add_row(
                "status",
                incident["fields"]["status"]["name"],
                new_data["status"],
            )

            for name, field in (
                ("summary", "summary"),
                ("severity", "customfield_10319"),
                ("detection method", "customfield_12881"),
                ("declare date", "customfield_15087"),
                ("impact start (ts)", "customfield_18693"),
                ("time declared (ts)", "customfield_18692"),
                ("time detected (ts)", "customfield_18694"),
                ("time alerted (ts)", "customfield_18695"),
                ("time acknowledged (ts)", "customfield_18696"),
                ("time responded (ts)", "customfield_18697"),
                ("time mitigated (ts)", "customfield_18698"),
                ("time resolved (ts)", "customfield_18699"),
            ):
                if name in ("severity", "detection method"):
                    current_value = {
                        "value": glom(incident, f"fields.{field}.value", default=None)
                    }
                else:
                    current_value = incident["fields"][field]

                current_value = str(current_value)
                new_value = str(updated_fields[field])

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
                if incident["fields"]["status"]["name"] != new_data["status"]:
                    update_jira_issue_status(
                        jira_base_url=url,
                        username=username,
                        password=password,
                        issue_key=incident_key,
                        new_status=new_data["status"],
                    )
                update_jira_issue_data(
                    jira_base_url=url,
                    username=username,
                    password=password,
                    issue_key=incident_key,
                    updated_fields=updated_fields,
                )

    click.echo("Done!")
