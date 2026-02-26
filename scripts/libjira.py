# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from typing import Optional, Union
import urllib

import arrow
from glom import glom
import requests
from requests.auth import HTTPBasicAuth


def convert_datestamp(datestamp):
    """Drop the timezone and convert to google sheets friendly datestamp.

    2025-01-31T15:06:00.000-0500 -> 2025-01-31 15:06:00

    """
    if not datestamp:
        return datestamp

    return datestamp[0:10] + " " + datestamp[11:19]


def extract_doc(incident: dict):
    def is_doc(url):
        return url and url.startswith("https://docs.google.com/document")

    description = glom(incident, "fields.description", default={})

    # Do a depth-first search with the assumption that the first doc listed is
    # the incident report
    content_nodes = description.get("content", [])
    while content_nodes:
        node = content_nodes.pop(0)
        if node["type"] == "inlineCard" and is_doc(node["attrs"]["url"]):
            return node["attrs"]["url"]
        if node["type"] == "text":
            marks = node.get("marks", [])
            for mark in marks:
                if mark["type"] != "link":
                    continue
                if is_doc(mark["attrs"]["href"]):
                    return mark["attrs"]["href"]
        content_nodes = node.get("content", []) + content_nodes

    return "no doc"


def fix_incident_data(jira_url, incident):
    return {
        "key": incident["key"],
        "jira_url": f"{jira_url}/browse/{incident['key']}",
        "status": incident["fields"]["status"]["name"],
        "summary": incident["fields"]["summary"],
        "severity": glom(incident, "fields.customfield_10319.value", default="undetermined"),
        "entities": glom(incident, "fields.customfield_18555", default="unknown").split(","),
        "report_url": extract_doc(incident),
        "declare date": glom(incident, "fields.customfield_15087", default=None),
        "impact start": glom(incident, "fields.customfield_15191", default=None),
        "detection method": glom(
            incident, "fields.customfield_12881.value", default=None
        ),
        "detected": glom(incident, "fields.customfield_12882", default=None),
        "alerted": glom(incident, "fields.customfield_12883", default=None),
        "acknowledged": glom(incident, "fields.customfield_12884", default=None),
        "responded": glom(incident, "fields.customfield_12885", default=None),
        "mitigated": glom(incident, "fields.customfield_12886", default=None),
        "resolved": glom(incident, "fields.customfield_12887", default=None),
    }


def get_arrow_time_or_none(incident, field, fieldname):
    value = glom(incident, f"fields.{field}", default="")
    if value:
        value = arrow.get(value)

    return value


def generate_jira_link(jira_url, incident_keys):
    base = f"{jira_url}/jira/software/c/projects/IIM/issues?"
    keys = ",".join(incident_keys)
    params = {"jql": f"project = IIM AND issuetype = Incident AND key in ({keys})"}
    return base + urllib.parse.urlencode(params)


def get_all_issues_for_project(
    jira_base_url: str,
    project_key: str,
    username: str,
    password: str,
    max_results: int = 100,
    fields: Union[str, list[str]] = "*all",
) -> list[dict]:
    """
    Fetch all Jira issues for a given project key (Jira Cloud) using the
    enhanced JQL search endpoint: GET /rest/api/3/search/jql.

    Returns: list of issue JSON objects.
    """
    issues: list[dict] = []
    next_page_token: Optional[str] = None

    auth = HTTPBasicAuth(username, password)
    headers = {"Accept": "application/json"}

    # Bounded JQL is recommended/required for some newer endpoints; ordering helps keep it stable.
    jql = f'project = "{project_key}" and issueType = "Incident" ORDER BY created ASC'

    while True:
        params = {
            "jql": jql,
            "maxResults": max_results,
            "fields": fields,
        }
        if next_page_token:
            params["nextPageToken"] = next_page_token

        resp = requests.get(
            f"{jira_base_url.rstrip('/')}/rest/api/3/search/jql",
            headers=headers,
            params=params,
            auth=auth,
            timeout=30,
        )
        resp.raise_for_status()

        data = resp.json()
        issues.extend(data.get("issues", []))

        # Enhanced search pagination: stop when isLast == True, otherwise
        # follow nextPageToken.
        if data.get("isLast") is True:
            break

        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            # Defensive: if Jira doesn't provide a token but also didn't say
            # it's last, stop to avoid looping.
            break

    return issues
