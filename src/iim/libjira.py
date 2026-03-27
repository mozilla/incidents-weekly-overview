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

from iim.libreport import ActionItem, IncidentReport, normalize_entities


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
    "impacted_entities": "customfield_18555",
}


def to_jira_field(field):
    return INCIDENT_REPORT_TO_JIRA_FIELD.get(field)


def fix_jira_incident_data(
    jira_url: str,
    incident: dict,
    remotelinks: Optional[list[dict]] = None,
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
        entities=normalize_entities(
            glom(incident, "fields.customfield_18555", default=None)
        ),
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


def get_arrow_time_or_none(incident: dict, field: str) -> Optional[arrow.Arrow]:
    value = glom(incident, f"fields.{field}", default=None)
    return arrow.get(value) if value else None


def generate_jira_link(jira_url: str, incident_keys: list[str]):
    base = f"{jira_url}/jira/software/c/projects/IIM/issues?"
    keys = ",".join(incident_keys)
    params = {"jql": f"project = IIM AND issuetype = Incident AND key in ({keys})"}
    return base + urllib.parse.urlencode(params)


class JiraAPI:
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
    ):
        self.base_url = base_url.rstrip("/")
        self.auth = HTTPBasicAuth(username, password)
        self.headers = {"Accept": "application/json"}

    def get_all_issues_for_project(
        self,
        project_key: str,
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

        # Bounded JQL is recommended/required for some newer endpoints; ordering helps keep it stable.
        jql = (
            f'project = "{project_key}" and issueType = "Incident" ORDER BY created ASC'
        )

        while True:
            params: dict = {
                "jql": jql,
                "maxResults": max_results,
                "fields": fields,
            }
            if next_page_token:
                params["nextPageToken"] = next_page_token

            resp = requests.get(
                f"{self.base_url}/rest/api/3/search/jql",
                headers=self.headers,
                params=params,
                auth=self.auth,
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

    def get_issue_remotelinks(self, issue_key: str) -> list[dict]:
        """
        Fetches remote links (external URL links) for a Jira issue.
        """
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/remotelink"
        response = requests.get(url, auth=self.auth, headers=self.headers, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_issue(self, issue_key: str) -> dict:
        """
        Requests Jira incident issue data.
        """
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}"
        response = requests.get(url, auth=self.auth, headers=self.headers, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_issue_report(self, issue_key: str) -> IncidentReport:
        """
        Fetches data for the Jira incident issue specified by issue_key.
        """
        data = self.get_issue(issue_key)
        remotelinks = self.get_issue_remotelinks(issue_key)
        return fix_jira_incident_data(
            jira_url=self.base_url,
            incident=data,
            remotelinks=remotelinks,
        )

    def update_issue_status(self, issue_key: str, new_status: str) -> None:
        """
        Update a Jira issue's status by transitioning it.

        :raises requests.HTTPError: if the request fails
        """
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/transitions"
        headers = {**self.headers, "Content-Type": "application/json"}

        # Step 1: Get available transitions
        response = requests.get(url, headers=headers, auth=self.auth, timeout=30)
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
            url, headers=headers, json=payload, auth=self.auth, timeout=30
        )
        if response.status_code not in (200, 204):
            print(response.json())
            response.raise_for_status()

    def update_issue_data(self, issue_key: str, updated_fields: dict) -> None:
        """
        Update a Jira issue with new field data.

        :raises requests.HTTPError: if the request fails
        """
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}"
        headers = {**self.headers, "Content-Type": "application/json"}
        payload = {"fields": updated_fields}

        response = requests.put(
            url, auth=self.auth, headers=headers, json=payload, timeout=30
        )
        # Jira returns 204 No Content on success
        if response.status_code not in (200, 204):
            print(response.json())
            response.raise_for_status()

    def add_issue_link(self, incident_key: str, linked_issue_key: str) -> None:
        """Create an 'Action item' issue link from incident_key to linked_issue_key."""
        url = f"{self.base_url}/rest/api/3/issueLink"
        headers = {**self.headers, "Content-Type": "application/json"}
        payload = {
            "type": {"name": "Action item"},
            "inwardIssue": {"key": incident_key},
            "outwardIssue": {"key": linked_issue_key},
        }
        response = requests.post(
            url, auth=self.auth, headers=headers, json=payload, timeout=30
        )
        # NOTE(willkg): Ignore 401 which occurs when we're trying to link to an
        # issue in an archived space.
        # FIXME(willkg): Ignore 404 which occurs when the token belongs to a
        # Jira account that doesn't have access to the issue being linked. Need
        # to figure out a better way to handle this.
        if response.status_code not in (200, 201, 401, 404):
            print(response.json())
            response.raise_for_status()

    def remove_issue_link(self, link_id: str) -> None:
        """Delete a Jira issue link by its ID."""
        url = f"{self.base_url}/rest/api/3/issueLink/{link_id}"
        response = requests.delete(
            url, auth=self.auth, headers=self.headers, timeout=30
        )
        if response.status_code not in (200, 204):
            print(response.json())
            response.raise_for_status()

    def add_remote_link(self, incident_key: str, action_item: ActionItem) -> None:
        """Create a remote link on a Jira issue for a non-Jira action item."""
        url = f"{self.base_url}/rest/api/3/issue/{incident_key}/remotelink"
        headers = {**self.headers, "Content-Type": "application/json"}
        payload = {
            "object": {
                "url": action_item.url,
                "title": action_item.essence(),
            }
        }
        response = requests.post(
            url, auth=self.auth, headers=headers, json=payload, timeout=30
        )
        if response.status_code not in (200, 201):
            print(response.json())
            response.raise_for_status()

    def remove_remote_link(self, incident_key: str, action_item: ActionItem) -> None:
        """Delete a remote link from a Jira issue using the link ID on the action item."""
        url = f"{self.base_url}/rest/api/3/issue/{incident_key}/remotelink/{action_item.jira_id}"
        response = requests.delete(
            url, auth=self.auth, headers=self.headers, timeout=30
        )
        if response.status_code not in (200, 204):
            print(response.json())
            response.raise_for_status()
