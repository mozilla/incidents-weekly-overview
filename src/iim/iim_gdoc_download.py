# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Download a Google Doc as a markdown file.
"""

import os
import re
import traceback

import click
from dotenv import load_dotenv

from iim.libgdoc import BadGdocId, build_service, download_gdoc
from iim.libjira import JiraAPI, extract_doc
from iim.libreport import jira_key


load_dotenv()


UNSAFE_CHARS_RE = re.compile(r"[^\w\s-]")
WHITESPACE_RE = re.compile(r"[\s_]+")


def title_to_filename(title):
    name = title.lower()
    name = UNSAFE_CHARS_RE.sub("", name)
    name = WHITESPACE_RE.sub("_", name)
    name = name.strip("_-")
    return name + ".md"


def resolve_gdoc_url(arg, jira_client):
    """Resolve an argument to a Google Doc URL.

    Accepts a Google Doc URL (returned as-is), a bare Jira key (IIM-123),
    or a Jira browse URL. For Jira references, fetches the issue and extracts
    the doc URL from its description.
    """
    key = jira_key(arg)
    if key is None:
        return arg

    if jira_client is None:
        raise click.UsageError(
            f"'{arg}' looks like a Jira key but JIRA_URL, JIRA_USERNAME, "
            "and JIRA_TOKEN are not all set in the environment."
        )

    click.echo(f"Resolving {key} from Jira...")
    issue = jira_client.get_issue(key)
    doc_url = extract_doc(issue["fields"]["description"])
    if doc_url == "no doc":
        raise click.ClickException(f"{key} has no Google Doc link in its description.")
    click.echo(f"  Found doc: {doc_url}")
    return doc_url


def _build_jira_client():
    """Build a JiraAPI client from environment variables, or return None."""
    jira_url = os.environ.get("JIRA_URL", "").strip()
    username = os.environ.get("JIRA_USERNAME", "").strip()
    token = os.environ.get("JIRA_TOKEN", "").strip()
    if jira_url and username and token:
        return JiraAPI(base_url=jira_url, username=username, password=token)
    return None


@click.command()
@click.option(
    "--client-secret-file",
    default="client_secret.json",
    show_default=True,
    type=click.Path(exists=True),
    help="Path to the OAuth2 client secret JSON file",
)
@click.option(
    "--output-dir",
    default="reports",
    show_default=True,
    type=click.Path(file_okay=False),
    help="Directory to save downloaded markdown files",
)
@click.argument("sources", nargs=-1)
def iim_gdoc_download(client_secret_file, output_dir, sources):
    """
    Download one or more Google Docs as markdown.

    SOURCES can be Google Doc URLs, Jira issue keys (e.g. IIM-123), or
    Jira browse URLs. For Jira references, the Google Doc URL is looked up
    from the issue description.

    If no arguments are provided, inputs are read one per line from stdin.

    See `README.md` for setup instructions.
    """
    if sources:
        args = list(sources)
    elif not click.get_text_stream("stdin").isatty():
        args = [line.strip() for line in click.get_text_stream("stdin") if line.strip()]
    else:
        raise click.UsageError("Provide SOURCES as arguments or pipe them via stdin.")

    jira_client = _build_jira_client()
    drive_service = build_service(client_secret_file)

    for arg in args:
        try:
            url = resolve_gdoc_url(arg, jira_client)
        except click.ClickException:
            raise
        except Exception:
            traceback.print_exc()
            click.echo(f"Unable to resolve '{arg}' to a Google Doc URL.")
            continue

        try:
            docname, content = download_gdoc(drive_service, url)
        except BadGdocId as exc:
            raise click.BadParameter(str(exc), param_hint="SOURCES")
        except Exception:
            traceback.print_exc()
            click.echo("Unable to download incident report.")
            continue

        os.makedirs(output_dir, exist_ok=True)
        output = os.path.join(output_dir, title_to_filename(docname))

        with open(output, "w") as f:
            f.write(content)
        click.echo(f"Saved to {output}")
