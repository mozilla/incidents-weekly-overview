# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import re

import marko
import marko.block
import marko.inline

from iim.libreport import IncidentReport


DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
DATETIME_RE = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2})")
JIRA_ISSUE_RE = re.compile(r"(IIM\-\d+)")
JIRA_URL_RE = re.compile(r"\[IIM-\d+\]\((https?://[^)]+)\)")
PLAIN_URL_RE = re.compile(r"(https?://\S+/browse/IIM-\d+)")


class NoJiraURLError(Exception):
    pass


class NoJiraKeyError(Exception):
    pass


def extract_jira_url(value):
    """Extract Jira URL from markdown link or plain URL"""
    url_match = JIRA_URL_RE.search(value) or PLAIN_URL_RE.search(value)
    if url_match:
        return url_match[1]
    raise NoJiraURLError(f"{value!r} has no jira url")


def extract_jira_key(url):
    key_match = JIRA_ISSUE_RE.search(url)
    if key_match:
        return key_match[0]
    raise NoJiraKeyError(f"{url!r} has no jira issue key")


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


# incident report field header -> data field
METADATA_LABEL_TO_FIELD = {
    "incident title": "summary",
    "incident severity": "severity",
    "jira ticket/bug number": "issues",
    "issue detected via": "detection_method",
    "current status": "status",
    "time declared": "declared",
    "time of first impact": "impact_start",
    "time detected": "detected",
    "time alerted": "alerted",
    "time acknowledged": "acknowledged",
    "time responded/engaged": "responded",
    "time mitigated (repaired)": "mitigated",
    "time resolved": "resolved",
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


def metadata_table_to_report(md):
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

    report = IncidentReport()

    # Jira issue key
    report.jira_url = extract_jira_url(md_table["issues"])
    report.key = extract_jira_key(report.jira_url)

    # Status
    status = md_table["status"].strip()
    # incident report has "please select", "ongoing", "mitigated", "resolved"
    # Jira incident has "detected", "in progress", "mitigated", "resolved"
    if status.lower().startswith("mitigated"):
        report.status = "Mitigated"
    elif status.lower().startswith("resolved"):
        report.status = "Resolved"
    else:
        report.status = "In Progress"

    # Severity fields.customfield_10319
    if "S1 - Critical" in md_table["severity"]:
        report.severity = "S1"
    elif "S2 - High" in md_table["severity"]:
        report.severity = "S2"
    elif "S3 - Medium" in md_table["severity"]:
        report.severity = "S3"
    elif "S4 - Low" in md_table["severity"]:
        report.severity = "S4"
    else:
        report.severity = None

    # Update detection method
    if "Manual/Human" in md_table["detection_method"]:
        report.detection_method = "Manual"
    elif "Automated Alert" in md_table["detection_method"]:
        report.detection_method = "Automation"
    else:
        report.detection_method = None

    # TODO: update services

    report.impact_start = extract_timestamp(md_table["impact_start"])
    report.declared = extract_timestamp(md_table.get("declared"))
    report.detected = extract_timestamp(md_table["detected"])
    report.alerted = extract_timestamp(md_table["alerted"])
    report.acknowledged = extract_timestamp(md_table["acknowledged"])
    report.responded = extract_timestamp(md_table["responded"])
    report.mitigated = extract_timestamp(md_table["mitigated"])
    report.resolved = extract_timestamp(md_table["resolved"])

    # declare date isn't in the table--we derive it from declared
    if report.declared:
        report.declare_date = report.declared.split("T")[0]

    return report


def parse_markdown(md):
    summary = None
    metadata_table = None
    action_items_table = None

    ast = marko.Markdown().parse(md)
    tokens = list(ast.children)
    while tokens:
        token = tokens.pop(0)
        if is_header(token):
            header_text = get_text(token)
            if header_text.startswith("Incident: "):
                summary = header_text.strip()[10:]
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

    # Parse metadata table and update report
    #
    # NOTE(willkg): the AST from the Markdown has this as a stream of tokens,
    # so we convert that back into the Markdown text and then re-tokenize it
    # because it's easier to deal with that way even if it is a bit silly
    metadata_table_text = get_text(metadata_table)
    report = metadata_table_to_report(metadata_table_text)
    report.summary = summary

    # FIXME(willkg): parse action_items_table and update report
    return report
