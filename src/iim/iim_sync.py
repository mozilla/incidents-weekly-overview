# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Sync a Jira incident issue with its Google Doc incident report.

Takes one or more Jira issue URLs, fetches each incident from Jira, downloads
its Google Doc report as markdown, computes the diff, and interactively lets
the user apply, skip, or retry each incident.
"""

import os
import traceback

import click
import requests
from dotenv import load_dotenv

from iim.libgdoc import BadGdocId, build_service, download_gdoc
from iim.libjira import JiraAPI
from iim.libreport import jira_key
from iim.libreportparser import NoJiraIIMKeyError, NoJiraIIMURLError, parse_markdown
from iim.libsync import (
    apply_changes,
    generate_actions_diff,
    generate_metadata_diff,
    generate_status_diff,
    print_diff_table,
)


load_dotenv()


@click.command()
@click.option(
    "--client-secret-file",
    default="client_secret.json",
    show_default=True,
    type=click.Path(exists=True),
    help="Path to the OAuth2 client secret JSON file",
)
@click.option(
    "--dry-run",
    default=False,
    is_flag=True,
    help="Show diff but do not push changes to Jira",
)
@click.argument("url_or_key", nargs=-1)
def iim_sync(client_secret_file: str, dry_run: bool, url_or_key: tuple[str, ...]):
    """
    Sync Jira incident issues with their Google Doc incident reports.

    URL_OR_KEY are full Jira issue browse URLs or bare issue keys, e.g.
    https://mozilla-hub.atlassian.net/browse/IIM-131 or IIM-131

    If not provided as arguments, URLs are read one per line from stdin.

    See `README.md` for setup instructions.
    """
    if url_or_key:
        urls = list(url_or_key)
    elif not click.get_text_stream("stdin").isatty():
        urls = [line.strip() for line in click.get_text_stream("stdin") if line.strip()]
    else:
        raise click.UsageError(
            "Provide URL_OR_KEY as arguments or pipe them via stdin."
        )

    jira_client = JiraAPI(
        base_url=os.environ["JIRA_URL"].strip(),
        username=os.environ["JIRA_USERNAME"].strip(),
        password=os.environ["JIRA_TOKEN"].strip(),
    )

    drive_service = build_service(client_secret_file)

    total = len(urls)
    for i, url in enumerate(urls, start=1):
        click.echo(f"Working on ({i}/{total}) {url} ...")

        # Step 1: extract issue key
        issue_key = jira_key(url)
        if not issue_key:
            click.echo(f"Error: Could not extract issue key from {url}. Skipping.")
            continue

        # Steps 2-8: per-incident retry loop
        while True:
            # Step 2: fetch Jira data
            try:
                jira_incident = jira_client.get_issue_report(issue_key)
            except requests.HTTPError as exc:
                click.echo(f"Error fetching {issue_key}: {exc}. Skipping.")
                break

            # Step 3: determine report URL
            report_url = jira_incident.report_url
            if not report_url or report_url == "no doc":
                click.echo(f"{issue_key}: No Google Doc found. Skipping.")
                break

            # Step 4: download the Google Doc
            try:
                _docname, md_data = download_gdoc(drive_service, report_url)
            except BadGdocId:
                click.echo(
                    f"Error: Could not extract doc ID from {report_url}. Skipping."
                )
                break
            except Exception:
                traceback.print_exc()
                click.echo("Unable to download incident report. Skipping.")
                break

            # Step 5: parse the markdown
            try:
                report_data = parse_markdown(md_data)
            except (NoJiraIIMKeyError, NoJiraIIMURLError):
                click.echo(
                    f"{issue_key}: Incident report doesn't have the Jira IIM key. Skipping."
                )
                break
            except (KeyError, IndexError):
                traceback.print_exc()
                click.echo("Error parsing document. Skipping.")
                break

            # Step 6: generate diff
            status_diff = generate_status_diff(jira_incident, report_data)
            metadata_diff = generate_metadata_diff(jira_incident, report_data)
            actions_diff = generate_actions_diff(jira_incident, report_data)
            all_diffs = status_diff + metadata_diff + actions_diff

            # Step 7: display
            has_changes = print_diff_table(jira_incident, all_diffs)

            # Step 8: interactive prompt
            if not has_changes:
                click.echo("Nothing to change.")

            if has_changes and not dry_run:
                click.echo("[S]kip  [ENTER] apply  [R]eload")
            else:
                click.echo("[S]kip  [R]eload")

            with open("/dev/tty") as tty:
                user_input = tty.readline().strip().lower()

            if user_input == "r":
                continue

            # 's' or ENTER/other: advance to next URL, applying if appropriate
            if has_changes and not dry_run and user_input != "s":
                # Step 9: apply changes
                click.echo("Committing to Jira ...")
                apply_changes(
                    jira_client, issue_key, status_diff, metadata_diff, actions_diff
                )
            break

    click.echo("Done!")
