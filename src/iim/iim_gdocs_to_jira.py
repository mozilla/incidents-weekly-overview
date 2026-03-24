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

from iim.libjira import JiraAPI
from iim.libreport import IncidentReport
from iim.libreportparser import NoJiraIIMURLError, NoJiraIIMKeyError, parse_markdown
from iim.libsync import (
    apply_changes,
    generate_actions_diff,
    generate_metadata_diff,
    generate_status_diff,
    print_diff_table,
)


load_dotenv()


class InvalidIncidentReport(Exception):
    pass


def read_markdown(fn: str) -> str:
    with open(fn, "r") as fp:
        md_data = fp.read()

    lines = md_data.strip().splitlines()
    for line in lines:
        if line.startswith("# ") and "Incident:" in line or "Incident report:" in line:
            break
    else:
        raise InvalidIncidentReport(f"{fn} is not an incident report")
    return md_data


@click.command()
@click.option("--dry-run", default=False, is_flag=True)
@click.argument("docs", nargs=-1)
@click.pass_context
def iim_google_docs_to_jira(ctx: click.Context, dry_run: bool, docs: tuple[str, ...]):
    """
    Prompts user for google doc metadata as markdown. Parses the markdown and
    extracts updated metadata and issue key. Pushes information to Jira.

    See `README.md` for setup instructions.
    """
    jira_client = JiraAPI(
        base_url=os.environ["JIRA_URL"].strip(),
        username=os.environ["JIRA_USERNAME"].strip(),
        password=os.environ["JIRA_TOKEN"].strip(),
    )

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
            with open("/dev/tty") as tty:
                tty.readline()
            continue
        except (NoJiraIIMKeyError, NoJiraIIMURLError):
            click.echo("Error: This incident report doesn't have the Jira IIM key.")
            click.echo("Next?")
            with open("/dev/tty") as tty:
                tty.readline()
            continue

        issue_key = markdown_report.key
        jira_incident: IncidentReport = jira_client.get_issue_report(issue_key)

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

        all_diffs = status_diff + metadata_diff + actions_diff
        changes = print_diff_table(jira_incident, markdown_report, all_diffs)

        if not changes:
            click.echo("Nothing to change.")
            click.echo("Next?")
            with open("/dev/tty") as tty:
                tty.readline()

        elif dry_run:
            click.echo("Dry-run mode. Pass without --dry-run to commit.")
            click.echo("Next?")
            with open("/dev/tty") as tty:
                tty.readline()

        else:
            click.echo("ENTER to commit, CTRL-C to exit, S to skip")
            with open("/dev/tty") as tty:
                user_input = tty.readline()
            if user_input.strip().lower() == "s":
                continue

            click.echo("Committing to Jira ...")
            apply_changes(
                jira_client, issue_key, status_diff, metadata_diff, actions_diff
            )

    click.echo("Done!")
