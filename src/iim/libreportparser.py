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
JIRA_URL_RE = re.compile(r"(https://\S+?/browse/IIM\-\d+)")


class NoJiraURLError(Exception):
    pass


class NoJiraKeyError(Exception):
    pass


def extract_jira_url(value):
    """Extract Jira URL from markdown link or plain URL"""
    url_match = JIRA_URL_RE.search(value)
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


def _table_to_rows(table_token):
    """
    Yield rows of the table as lists of (str | inline token) items.
    Handles both SoftBreak/LineBreak tokens and \\n embedded in RawText.
    """
    current = []
    for child in table_token.children:
        if isinstance(child, marko.inline.LineBreak):
            yield current
            current = []
        elif isinstance(child, (marko.inline.RawText, marko.inline.Literal)):
            lines = child.children.split("\n")
            for i, line in enumerate(lines):
                if i > 0:
                    yield current
                    current = []
                if line:
                    current.append(line)
        else:
            current.append(child)
    if current:
        yield current


def _row_to_cells(row_items):
    """
    Split row items into cells at | boundaries in string items.
    Returns list of cells; each cell is a list of (str | inline token).
    """
    cells = [[]]
    for item in row_items:
        if isinstance(item, str):
            parts = item.split("|")
            for i, part in enumerate(parts):
                if i > 0:
                    cells.append([])
                if part:
                    cells[-1].append(part)
        else:
            cells[-1].append(item)
    return cells


def _cell_text(cell_items):
    """Extract plain text from a cell (list of str | inline token)."""
    parts = []
    for item in cell_items:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(
            item, (marko.inline.RawText, marko.inline.Literal, marko.inline.CodeSpan)
        ):
            parts.append(item.children)
        elif hasattr(item, "children"):
            if isinstance(item.children, list):
                parts.append(_cell_text(item.children))
            elif isinstance(item.children, str):
                parts.append(item.children)
    return "".join(parts)


def _cell_link_dests(cell_items):
    """Yield all Link dests found in cell items."""
    for item in cell_items:
        if isinstance(item, marko.inline.Link):
            yield item.dest
        if hasattr(item, "children") and isinstance(item.children, list):
            yield from _cell_link_dests(item.children)


def metadata_table_to_report(table_token):
    """Parse a table-like Paragraph token into an IncidentReport."""
    md_table = {}
    for row_items in _table_to_rows(table_token):
        cells = _row_to_cells(row_items)
        if len(cells) < 3:
            continue

        label_text = _cell_text(cells[1]).lower().strip()

        field = None
        for key, val in METADATA_LABEL_TO_FIELD.items():
            if key in label_text:
                field = val
                break
        if field is None:
            continue

        value_cell = cells[2]
        if field == "issues":
            # Cells may have multiple links; find the first IIM URL
            iim_url = None
            for dest in _cell_link_dests(value_cell):
                try:
                    iim_url = extract_jira_url(dest)
                    break
                except NoJiraURLError:
                    continue
            md_table[field] = iim_url or _cell_text(value_cell).strip()
        else:
            md_table[field] = _cell_text(value_cell)

    report = IncidentReport()

    # Jira URL and key
    report.jira_url = extract_jira_url(md_table.get("issues", ""))
    report.key = extract_jira_key(report.jira_url)

    # Status
    # incident report has "please select", "ongoing", "mitigated", "resolved"
    # Jira incident has "detected", "in progress", "mitigated", "resolved"
    status = md_table.get("status", "").strip()
    if status.lower().startswith("mitigated"):
        report.status = "Mitigated"
    elif status.lower().startswith("resolved"):
        report.status = "Resolved"
    else:
        report.status = "In Progress"

    # Severity
    severity = md_table.get("severity", "")
    if "S1 - Critical" in severity:
        report.severity = "S1"
    elif "S2 - High" in severity:
        report.severity = "S2"
    elif "S3 - Medium" in severity:
        report.severity = "S3"
    elif "S4 - Low" in severity:
        report.severity = "S4"
    else:
        report.severity = None

    # Detection method
    detection_method = md_table.get("detection_method", "")
    if "Manual/Human" in detection_method:
        report.detection_method = "Manual"
    elif "Automated Alert" in detection_method:
        report.detection_method = "Automation"
    else:
        report.detection_method = None

    # TODO: update services

    report.impact_start = extract_timestamp(md_table.get("impact_start"))
    report.declared = extract_timestamp(md_table.get("declared"))
    report.alerted = extract_timestamp(md_table.get("alerted"))
    report.acknowledged = extract_timestamp(md_table.get("acknowledged"))
    report.responded = extract_timestamp(md_table.get("responded"))
    report.mitigated = extract_timestamp(md_table.get("mitigated"))
    report.resolved = extract_timestamp(md_table.get("resolved"))

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
    report = metadata_table_to_report(metadata_table)
    report.summary = summary

    # FIXME(willkg): parse action_items_table and update report
    return report
