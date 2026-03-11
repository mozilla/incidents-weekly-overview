# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Convert incident reports (as markdown) to field data and push to Jira.
"""

import copy
import os
import re
from typing import Dict

import click
from dotenv import load_dotenv
from glom import glom
import marko
import requests
from requests.auth import HTTPBasicAuth
import rich
from rich.table import Table

from iim.libjira import extract_doc


load_dotenv()


DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
DATETIME_RE = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2})")
JIRA_ISSUE_RE = re.compile(r"(IIM\-\d+)")


def extract_jira_issue(value):
    """Extract Jira issue key"""
    match = JIRA_ISSUE_RE.search(value)
    if match:
        return match[0]
    raise Exception(f"{value!r} has no jira issue key")


def extract_timestamp(value):
    """Extract datetime or date and return in YYYY-MM-DD hh:mm format"""
    if value is None:
        return None

    match = DATETIME_RE.search(value)
    if match:
        return match[0]

    match = DATE_RE.search(value)
    if match:
        return match[0] + " 00:00"
    return None


def get_issue_data(
    jira_base_url: str,
    username: str,
    password: str,
    issue_key: str,
) -> Dict:
    """
    Fetches data for the Jira incident issue specified by incident_key.
    """

    auth = HTTPBasicAuth(username, password)
    headers = {"Accept": "application/json"}

    url = f"{jira_base_url.rstrip('/')}/rest/api/3/issue/{issue_key}"

    response = requests.get(
        url,
        auth=auth,
        headers=headers,
        timeout=30,
    )

    # Raise an exception for 4xx/5xx responses
    response.raise_for_status()

    return response.json()


def update_jira_issue_status(
    jira_base_url: str,
    username: str,
    password: str,
    issue_key: str,
    new_status: str,
):
    """
    Update a Jira issue's status by transitioning it.

    :raises requests.HTTPError: if the request fails
    """
    url = f"{jira_base_url.rstrip('/')}/rest/api/3/issue/{issue_key}/transitions"

    auth = HTTPBasicAuth(username, password)
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    # Step 1: Get available transitions
    response = requests.get(
        url,
        headers=headers,
        auth=auth,
        timeout=30,
    )

    if response.status_code not in (200, 204):
        response.raise_for_status()

    transitions = response.json().get("transitions", [])

    # Step 2: Find matching transition by status name
    transition_id = None
    for transition in transitions:
        if transition["to"]["name"].lower() == new_status.lower():
            transition_id = transition["id"]
            break

    if not transition_id:
        available = [t["to"]["name"] for t in transitions]
        raise ValueError(
            f"Status '{new_status}' is not a valid transition for {issue_key}. "
            f"Available transitions: {available}"
        )

    # Step 3: Perform transition
    payload = {"transition": {"id": transition_id}}

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        auth=auth,
        timeout=30,
    )

    if response.status_code not in (200, 204):
        response.raise_for_status()


def update_jira_issue_data(
    jira_base_url: str,
    username: str,
    password: str,
    issue_key: str,
    updated_fields: dict,
) -> None:
    """
    Update a Jira issue with new field data.

    :raises requests.HTTPError: if the request fails
    """
    url = f"{jira_base_url.rstrip('/')}/rest/api/3/issue/{issue_key}"

    auth = HTTPBasicAuth(username, password)
    headers = {"Accept": "application/json"}
    payload = {
        "fields": updated_fields,
    }

    response = requests.put(
        url,
        auth=auth,
        headers=headers,
        json=payload,
        timeout=30,
    )

    # Jira returns 204 No Content on success
    if response.status_code not in (200, 204):
        response.raise_for_status()


# incident report field header -> data field
METADATA_LABEL_TO_FIELD = {
    "incident title": "summary",
    "incident severity": "severity",
    "jira ticket/bug number": "issues",
    "issue detected via": "detection method",
    "current status": "status",
    "time declared": "declared",
    "time of first impact": "impact start",
    "time detected": "detected",
    "time alerted": "alerted",
    "time acknowledged": "acknowledged",
    "time responded/engaged": "responded",
    "time mitigated (repaired)": "mitigated",
    "time resolved": "resolved",
}


DEFAULT_DATA = {
    "key": None,
    "summary": None,
    "severity": None,
    "detection method": None,
    "status": None,
    "declare date": None,
    # timestamps in UTC in YYYY-MM-DD HH:MM format
    "impact start": None,
    "declared": None,
    "detected": None,
    "alerted": None,
    "acknowledged": None,
    "responded": None,
    "mitigated": None,
    "resolved": None,
}


def is_header(token):
    return (
        isinstance(token, marko.block.Heading)
        and token.children
        and isinstance(token.children[0], marko.inline.RawText)
    )


def is_table(token):
    return (
        isinstance(token, marko.block.Paragraph)
        and token.children
        and token.children[0].children
        and isinstance(token.children[0].children, str)
        and token.children[0].children.startswith("|")
    )


def get_text(token):
    text = []
    if isinstance(
        token,
        (
            marko.inline.CodeSpan,
            marko.inline.LineBreak,
            marko.inline.Literal,
            marko.inline.RawText,
        ),
    ):
        text.append(token.children)
    elif isinstance(token, marko.inline.Link):
        link_text = []
        for child in token.children:
            link_text.extend(get_text(child))
        text.append(f"[{''.join(link_text) or 'Link'}]({token.dest})")
    else:
        for child in token.children:
            text.extend(get_text(child))

    return "".join(text)


def md_to_dict(md):
    data = copy.deepcopy(DEFAULT_DATA)

    metadata_table = None
    action_items_table = None

    ast = marko.Markdown().parse(md)
    tokens = ast.children
    while tokens:
        token = tokens.pop(0)
        if is_header(token):
            header_text = get_text(token)
            if header_text.startswith("Incident: "):
                data["summary"] = header_text.strip()[10:]
                while tokens:
                    token = tokens.pop(0)
                    if is_table(token):
                        metadata_table = token
                        break

            if header_text.startswith("Postmortem Action Items"):
                while tokens:
                    token = tokens.pop(0)
                    if is_table(token):
                        action_items_table = token  # noqa: F841
                        break

    # Parse metadata table and update data
    #
    # NOTE(willkg): the AST from the Markdown has this as a stream of tokens,
    # so we convert that back into the Markdown text and then re-tokenize it
    # because it's easier to deal with that way even if it is a bit silly
    metadata_table_text = get_text(metadata_table)
    data.update(metadata_table_to_dict(metadata_table_text))

    # FIXME(willkg): parse action_items_table and update data
    return data


def metadata_table_to_dict(md):
    # Convert Markdown text table to Python dict
    md_table = {}
    for line in md.splitlines():
        line = line.strip()
        if not line:
            continue
        line = line.split("|")
        label = line[1].lower().replace("*", "").strip()
        for key, val in METADATA_LABEL_TO_FIELD.items():
            if key in label:
                field = val
                break
        else:
            continue
        value = line[2]

        md_table[field] = value

    data = {}

    # Jira issue key
    data["key"] = extract_jira_issue(md_table["issues"])

    # Status
    status = md_table["status"].strip()
    # incident report has "please select", "ongoing", "mitigated", "resolved"
    # Jira incident has "detected", "in progress", "mitigated", "resolved"
    if status.lower().startswith("mitigated"):
        data["status"] = "Mitigated"
    elif status.lower().startswith("resolved"):
        data["status"] = "Resolved"
    else:
        data["status"] = "In Progress"

    # Severity fields.customfield_10319
    if "S1 - Critical" in md_table["severity"]:
        data["severity"] = {"value": "S1"}
    elif "S2 - High" in md_table["severity"]:
        data["severity"] = {"value": "S2"}
    elif "S3 - Medium" in md_table["severity"]:
        data["severity"] = {"value": "S3"}
    elif "S4 - Low" in md_table["severity"]:
        data["severity"] = {"value": "S4"}
    else:
        data["severity"] = None

    # Update detection method
    if "Manual/Human" in md_table["detection method"]:
        data["detection method"] = {"value": "Manual"}
    elif "Automated Alert" in md_table["detection method"]:
        data["detection method"] = {"value": "Automation"}
    else:
        data["detection method"] = None

    # TODO: update services

    data["impact start"] = extract_timestamp(md_table["impact start"])
    data["declared"] = extract_timestamp(md_table.get("declared"))
    data["detected"] = extract_timestamp(md_table["detected"])
    data["alerted"] = extract_timestamp(md_table["alerted"])
    data["acknowledged"] = extract_timestamp(md_table["acknowledged"])
    data["responded"] = extract_timestamp(md_table["responded"])
    data["mitigated"] = extract_timestamp(md_table["mitigated"])
    data["resolved"] = extract_timestamp(md_table["resolved"])

    # declare date isn't in the table--we derive it from declared
    if data["declared"]:
        data["declare date"] = data["declared"].split("T")[0]

    return data


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

            new_data = md_to_dict(md_data)

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
