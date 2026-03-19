# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from typing import Any, Optional, Union
import urllib
import urllib.parse

import arrow
from glom import glom
import requests
from requests.auth import HTTPBasicAuth

from iim.libreport import ActionItem, IncidentReport


def convert_datestamp(datestamp: str) -> str:
    """Drop the timezone and convert to google sheets friendly datestamp.

    2025-01-31T15:06:00.000-0500 -> 2025-01-31 15:06:00

    """
    if not datestamp:
        return datestamp

    return datestamp[0:10] + " " + datestamp[11:19]


def extract_doc(description: Any) -> str:
    def is_doc(url):
        return url and url.startswith("https://docs.google.com/document")

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


INCIDENT_REPORT_TO_JIRA_FIELD = {
    "status": "status",
    "summary": "summary",
    "severity": "customfield_10319",
    "entities": "customfield_18555",
    "declare_date": "customfield_15087",
    "detection_method": "customfield_12881",
    "impact_start": "customfield_18693",
    "declared": "customfield_18692",
    "detected": "customfield_18694",
    "alerted": "customfield_18695",
    "acknowledged": "customfield_18696",
    "responded": "customfield_18697",
    "mitigated": "customfield_18698",
    "resolved": "customfield_18699",
}


def to_jira_field(field):
    return INCIDENT_REPORT_TO_JIRA_FIELD.get(field)


def fix_jira_incident_data(
    jira_url: str, incident: dict, remotelinks: Optional[list[dict]] = None
) -> IncidentReport:
    action_items = []

    # Add "has action item" issue links
    issuelinks = glom(incident, "fields.issuelinks", default=[]) or []
    action_items.extend(
        [
            ActionItem(
                jira_id=item["id"],
                url=f"{jira_url}/browse/{item['outwardIssue']['key']}",
                status=item["outwardIssue"]["fields"]["status"]["name"],
                title=item["outwardIssue"]["fields"]["summary"],
            )
            for item in issuelinks
            if item["type"]["name"] == "Action item" and "outwardIssue" in item
        ]
    )

    # Add remote links (external URLs) that are action items
    for item in remotelinks or []:
        obj = item.get("object", {})
        url = obj.get("url")
        title = obj.get("title", "")

        if url and title.lower().startswith("action: "):
            action_items.append(
                ActionItem.from_essence(url=url, title=title, jira_id=str(item["id"]))
            )

    return IncidentReport(
        key=incident["key"],
        jira_url=f"{jira_url}/browse/{incident['key']}",
        status=incident["fields"]["status"]["name"],
        summary=incident["fields"]["summary"],
        description=incident["fields"]["description"],
        severity=glom(
            incident, "fields.customfield_10319.value", default="undetermined"
        ),
        entities=glom(incident, "fields.customfield_18555", default="unknown"),
        report_url=extract_doc(incident["fields"]["description"]),
        declare_date=glom(incident, "fields.customfield_15087", default=None),
        detection_method=glom(incident, "fields.customfield_12881.value", default=None),
        impact_start=glom(incident, "fields.customfield_18693", default=None),
        declared=glom(incident, "fields.customfield_18692", default=None),
        detected=glom(incident, "fields.customfield_18694", default=None),
        alerted=glom(incident, "fields.customfield_18695", default=None),
        acknowledged=glom(incident, "fields.customfield_18696", default=None),
        responded=glom(incident, "fields.customfield_18697", default=None),
        mitigated=glom(incident, "fields.customfield_18698", default=None),
        resolved=glom(incident, "fields.customfield_18699", default=None),
        action_items=action_items,
    )


def get_arrow_time_or_none(incident: dict, field: str, fieldname: str) -> arrow.Arrow:
    value = glom(incident, f"fields.{field}", default="")
    if value:
        value = arrow.get(value)

    return value


def generate_jira_link(jira_url: str, incident_keys: list[str]):
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


def get_issue_remotelinks(
    jira_base_url: str,
    username: str,
    password: str,
    issue_key: str,
) -> list[dict]:
    """
    Fetches remote links (external URL links) for a Jira issue.
    """
    auth = HTTPBasicAuth(username, password)
    headers = {"Accept": "application/json"}
    url = f"{jira_base_url.rstrip('/')}/rest/api/3/issue/{issue_key}/remotelink"

    response = requests.get(url, auth=auth, headers=headers, timeout=30)
    response.raise_for_status()

    return response.json()


def get_issue(
    jira_base_url: str,
    username: str,
    password: str,
    issue_key: str,
) -> dict:
    """
    Requests Jira incident issue data.
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


def get_issue_report(
    jira_base_url: str,
    username: str,
    password: str,
    issue_key: str,
) -> IncidentReport:
    """
    Fetches data for the Jira incident issue specified by incident_key.
    """
    data = get_issue(
        jira_base_url=jira_base_url,
        username=username,
        password=password,
        issue_key=issue_key,
    )
    remotelinks = get_issue_remotelinks(
        jira_base_url=jira_base_url,
        username=username,
        password=password,
        issue_key=issue_key,
    )

    return fix_jira_incident_data(
        jira_url=jira_base_url, incident=data, remotelinks=remotelinks
    )


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


def add_jira_issue_link(
    jira_base_url: str,
    username: str,
    password: str,
    incident_key: str,
    linked_issue_key: str,
) -> None:
    """Create an 'Action item' issue link from incident_key to linked_issue_key."""
    url = f"{jira_base_url.rstrip('/')}/rest/api/3/issueLink"
    auth = HTTPBasicAuth(username, password)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    payload = {
        "type": {"name": "Action item"},
        "inwardIssue": {"key": incident_key},
        "outwardIssue": {"key": linked_issue_key},
    }
    response = requests.post(url, auth=auth, headers=headers, json=payload, timeout=30)
    if response.status_code not in (200, 201):
        response.raise_for_status()


def remove_jira_issue_link(
    jira_base_url: str,
    username: str,
    password: str,
    link_id: str,
) -> None:
    """Delete a Jira issue link by its ID."""
    url = f"{jira_base_url.rstrip('/')}/rest/api/3/issueLink/{link_id}"
    auth = HTTPBasicAuth(username, password)
    headers = {"Accept": "application/json"}
    response = requests.delete(url, auth=auth, headers=headers, timeout=30)
    if response.status_code not in (200, 204):
        response.raise_for_status()


def add_remote_link(
    jira_base_url: str,
    username: str,
    password: str,
    incident_key: str,
    action_item: ActionItem,
) -> None:
    """Create a remote link on a Jira issue for a non-Jira action item."""
    url = f"{jira_base_url.rstrip('/')}/rest/api/3/issue/{incident_key}/remotelink"
    auth = HTTPBasicAuth(username, password)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    payload = {
        "object": {
            "url": action_item.url,
            "title": action_item.essence(),
        }
    }
    response = requests.post(url, auth=auth, headers=headers, json=payload, timeout=30)
    if response.status_code not in (200, 201):
        response.raise_for_status()


def remove_remote_link(
    jira_base_url: str,
    username: str,
    password: str,
    incident_key: str,
    action_item: ActionItem,
) -> None:
    """Delete a remote link from a Jira issue using the link ID on the action item."""
    url = f"{jira_base_url.rstrip('/')}/rest/api/3/issue/{incident_key}/remotelink/{action_item.jira_id}"
    auth = HTTPBasicAuth(username, password)
    headers = {"Accept": "application/json"}
    response = requests.delete(url, auth=auth, headers=headers, timeout=30)
    if response.status_code not in (200, 204):
        response.raise_for_status()
