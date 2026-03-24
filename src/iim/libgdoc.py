# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Shared Google Drive utilities.
"""

import io
import os
import re

import arrow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
TOKEN_FILE = os.path.join(".gdrive", "oauth_token.json")


DOC_ID_RE = re.compile(r"/document/d/([a-zA-Z0-9_-]+)")


def extract_doc_id(url):
    match = DOC_ID_RE.search(url)
    if not match:
        raise ValueError(f"Could not extract document ID from URL: {url}")
    return match.group(1)


class BadGdocId(Exception):
    pass


def download_gdoc(drive_service, url):
    try:
        doc_id = extract_doc_id(url)
    except ValueError as e:
        raise BadGdocId(str(e))

    meta = (
        drive_service.files()
        .get(fileId=doc_id, fields="name", supportsAllDrives=True)
        .execute()
    )

    docname = meta["name"]

    request = drive_service.files().export_media(
        fileId=doc_id, mimeType="text/x-markdown"
    )

    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()

    content = buffer.getvalue().decode("utf-8")

    return docname, content


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


def build_service(client_secret_file):
    creds = get_credentials(client_secret_file)
    return build("drive", "v3", credentials=creds)


def get_doc_modified_time(drive_service, report_url):
    if not drive_service or not report_url or report_url == "no doc":
        return None
    try:
        doc_id = extract_doc_id(report_url)
    except ValueError:
        return None
    try:
        meta = (
            drive_service.files()
            .get(fileId=doc_id, fields="modifiedTime", supportsAllDrives=True)
            .execute()
        )
        modified = meta.get("modifiedTime")
        return arrow.get(modified).format("YYYY-MM-DD HH:mm")
    except Exception:
        return None


def update_report(drive_service, report):
    if drive_service and report.report_url:
        report.report_modified = get_doc_modified_time(drive_service, report.report_url)
    return report
