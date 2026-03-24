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

from iim.libgdoc import BadGdocId, build_service, download_gdoc


UNSAFE_CHARS_RE = re.compile(r"[^\w\s-]")
WHITESPACE_RE = re.compile(r"[\s_]+")


def title_to_filename(title):
    name = title.lower()
    name = UNSAFE_CHARS_RE.sub("", name)
    name = WHITESPACE_RE.sub("_", name)
    name = name.strip("_-")
    return name + ".md"


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
@click.argument("gdoc_urls", nargs=-1)
def iim_gdoc_download(client_secret_file, output_dir, gdoc_urls):
    """
    Download one or more Google Docs as markdown.

    GDOC_URLS are the URLs of the Google Docs to download. If not provided,
    URLs are read one per line from stdin.
    """
    if gdoc_urls:
        urls = list(gdoc_urls)
    elif not click.get_text_stream("stdin").isatty():
        urls = [line.strip() for line in click.get_text_stream("stdin") if line.strip()]
    else:
        raise click.UsageError("Provide GDOC_URLS as arguments or pipe them via stdin.")

    drive_service = build_service(client_secret_file)

    for url in urls:
        try:
            docname, content = download_gdoc(drive_service, url)
        except BadGdocId as exc:
            raise click.BadParameter(str(exc), param_hint="GDOC_URLS")
        except Exception:
            traceback.print_exc()
            click.echo("Unable to download incident report.")
            continue

        os.makedirs(output_dir, exist_ok=True)
        output = os.path.join(output_dir, title_to_filename(docname))

        with open(output, "w") as f:
            f.write(content)
        click.echo(f"Saved to {output}")
