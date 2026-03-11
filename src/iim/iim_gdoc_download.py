# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Download a Google Doc as a markdown file.
"""

import io
import os
import re

import click
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

DOC_ID_RE = re.compile(r"/document/d/([a-zA-Z0-9_-]+)")
UNSAFE_CHARS_RE = re.compile(r"[^\w\s-]")
WHITESPACE_RE = re.compile(r"[\s_]+")


def title_to_filename(title):
    name = title.lower()
    name = UNSAFE_CHARS_RE.sub("", name)
    name = WHITESPACE_RE.sub("_", name)
    name = name.strip("_-")
    return name + ".md"


def extract_doc_id(url):
    match = DOC_ID_RE.search(url)
    if not match:
        raise ValueError(f"Could not extract document ID from URL: {url}")
    return match.group(1)


TOKEN_FILE = os.path.join(".gdrive", "oauth_token.json")


def get_credentials(client_secret_file):
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, SCOPES)
            creds = flow.run_local_server(port=0)

        os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return creds


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

    creds = get_credentials(client_secret_file)
    service = build("drive", "v3", credentials=creds)

    for url in urls:
        try:
            doc_id = extract_doc_id(url)
        except ValueError as e:
            raise click.BadParameter(str(e), param_hint="GDOC_URLS")

        meta = (
            service.files()
            .get(fileId=doc_id, fields="name", supportsAllDrives=True)
            .execute()
        )
        os.makedirs(output_dir, exist_ok=True)
        output = os.path.join(output_dir, title_to_filename(meta["name"]))

        request = service.files().export_media(
            fileId=doc_id, mimeType="text/x-markdown"
        )

        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        content = buffer.getvalue().decode("utf-8")

        with open(output, "w") as f:
            f.write(content)
        click.echo(f"Saved to {output}")
