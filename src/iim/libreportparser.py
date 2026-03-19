# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import re
from urllib.parse import urlsplit

import marko
import marko.block
import marko.inline

from iim.libreport import ActionItem, IncidentReport


DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
DATETIME_RE = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2})")
ISO_DATETIME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})")
JIRA_ISSUE_RE = re.compile(r"(IIM\-\d+)")
JIRA_URL_RE = re.compile(r"(https://\S+?/browse/IIM\-\d+)")


class NoJiraIIMURLError(Exception):
    pass


def extract_jira_iim_url(value: str) -> str:
    """Extract Jira URL from markdown link or plain URL"""
    url_match = JIRA_URL_RE.search(value)
    if url_match:
        return url_match[1]
    raise NoJiraIIMURLError(f"{value!r} has no jira url")


class NoJiraIIMKeyError(Exception):
    pass


def extract_jira_key(url: str) -> str:
    parts = urlsplit(url)
    if not parts.path.startswith("/browse/"):
        raise NoJiraIIMKeyError(f"{url!r} has no jira issue key")

    return parts.path.split("/")[-1]


def extract_timestamp(value):
    """Extract datetime or date and return in YYYY-MM-DD hh:mm format"""
    if value is None:
        return None

    match = ISO_DATETIME_RE.search(value)
    if match:
        return f"{match[1]} {match[2]}"

    match = DATETIME_RE.search(value)
    if match:
        return match[0]

    match = DATE_RE.search(value)
    if match:
        return match[0] + " 00:00"
    return None


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


def get_text(token, keep_links: bool = True):
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
            link_text.extend(get_text(child, keep_links=keep_links))
        if keep_links:
            text.append(f"[{''.join(link_text) or 'Link'}]({token.dest})")
        else:
            text.append("".join(link_text) or "Link")
    else:
        for child in token.children:
            text.extend(get_text(child, keep_links=keep_links))

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


def _recursive_link_dests(token):
    """Yield all Link dests found recursively in any token (block or inline)."""
    if isinstance(token, marko.inline.Link):
        yield token.dest
    if hasattr(token, "children") and isinstance(token.children, list):
        for child in token.children:
            yield from _recursive_link_dests(child)


def normalize_entities(value: str | None) -> str | None:
    """Normalize a comma-separated entities string to sorted, lowercased, ', '-delimited form."""
    if not value or not value.strip():
        return None
    parts = [p.strip().lower() for p in value.split(",") if p.strip()]
    return ", ".join(sorted(parts))


class ReportParser:
    def parse_markdown(self, report, md):
        return report


class ReportParser20250520(ReportParser):
    TEMPLATE_VERSION = "2025.05.20"

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
        "time acknowledge": "acknowledged",
        "time acknowledged": "acknowledged",
        "time responded/engaged": "responded",
        "time mitigated (repaired)": "mitigated",
        "time resolved": "resolved",
    }

    def metadata_table_to_report(self, report: IncidentReport, table_token):
        """Parse a table-like Paragraph token and update IncidentReport report."""
        md_table = {}
        for row_items in _table_to_rows(table_token):
            cells = _row_to_cells(row_items)
            if len(cells) < 3:
                continue

            label_text = _cell_text(cells[1]).lower().strip()

            field = None
            for key, val in self.METADATA_LABEL_TO_FIELD.items():
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
                        iim_url = extract_jira_iim_url(dest)
                        break
                    except NoJiraIIMURLError:
                        continue
                md_table[field] = iim_url or _cell_text(value_cell).strip()
            else:
                md_table[field] = _cell_text(value_cell)

        # Jira URL and key
        report.jira_url = extract_jira_iim_url(md_table.get("issues", ""))
        report.key = extract_jira_key(report.jira_url)

        # Status
        # incident report has "please select", "ongoing", "mitigated", "resolved"
        # Jira incident has "detected", "in progress", "mitigated", "resolved"
        status = md_table.get("status", "").strip()
        if status.lower().startswith("mitigated"):
            report.status = "Mitigated"
        elif status.lower().startswith(("resolved", "done")):
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

    def _extract_action_item_status(self, cell_items):
        """Extract status string from action item ticket cell.

        Handles formats like:
        [MNTOR-5235](url) Status: Done
        [[MZCLD-806](url)] **Done**
        **In Progress**
        Status: Not started
        """
        cell_text = _cell_text(cell_items)

        # Explicit "Status: X" pattern
        if "Status:" in cell_text:
            return cell_text.split("Status:", 1)[1].strip().upper()

        # Collect non-link text (handles bold status like **Done**)
        parts = []
        for item in cell_items:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, (marko.inline.RawText, marko.inline.Literal)):
                parts.append(item.children)
            elif isinstance(item, marko.inline.Link):
                pass  # skip link content
            elif hasattr(item, "children") and isinstance(item.children, list):
                parts.append(_cell_text(item.children))

        non_link_text = re.sub(r"[\[\]\s]+", " ", "".join(parts)).strip() or "unknown"
        return non_link_text.upper()

    def action_items_table_to_report(self, report: IncidentReport, table_token):
        """Parse action items table token and update IncidentReport report."""
        if table_token is None:
            return

        report.action_items = []
        for row_items in _table_to_rows(table_token):
            cells = _row_to_cells(row_items)
            if len(cells) < 3:
                continue

            ticket_cell = cells[1]
            ticket_text = _cell_text(ticket_cell).strip()

            # Title is the first line of non-empty title cell
            title_cell = cells[2]
            title = _cell_text(title_cell).strip()
            if title:
                title = title.splitlines()[0]

            # Skip header and separator rows
            if not title and not ticket_text:
                continue
            if re.match(r"^[\s:\-]+$", ticket_text):
                continue
            if "jira ticket" in ticket_text.lower() or "ticket title" in title.lower():
                continue

            url = next(_cell_link_dests(ticket_cell), None)
            # Drop action items whose URL is a mailto or the template placeholder
            if url and url.startswith("mailto:"):
                continue
            if url == "https://mozilla-hub.atlassian.net/browse/":
                continue
            status = self._extract_action_item_status(ticket_cell)

            report.action_items.append(ActionItem(url=url, status=status, title=title))

    def parse_markdown(self, report, md):
        report.template_version = self.TEMPLATE_VERSION

        metadata_table = None
        action_items_table = None
        ast = marko.Markdown().parse(md)
        tokens = list(ast.children)
        while tokens:
            token = tokens.pop(0)
            if is_header(token):
                header_text = get_text(token, keep_links=False)
                if "Incident: " in header_text or "Incident report: " in header_text:
                    report.summary = header_text.strip()[10:]
                    while tokens:
                        token = tokens.pop(0)
                        if is_table(token):
                            metadata_table = token
                            break

                if header_text.startswith("Postmortem Action Items"):
                    while tokens:
                        token = tokens.pop(0)
                        if is_table(token):
                            action_items_table = token
                            break

        # Parse metadata table and update report
        self.metadata_table_to_report(report, metadata_table)

        # Parse action item table and update report
        self.action_items_table_to_report(report, action_items_table)
        return report


class ReportParser20260312(ReportParser20250520):
    TEMPLATE_VERSION = "2026.03.12"

    METADATA_LABEL_TO_FIELD = {
        "incident severity": "severity",
        "jira ticket/bug number": "issues",
        "detection method": "detection_method",
        "current status": "status",
        "time declared": "declared",
        "time of first impact": "impact_start",
        "time alerted": "alerted",
        "time acknowledged": "acknowledged",
        "time responded/engaged": "responded",
        "time mitigated (repaired)": "mitigated",
        "time resolved": "resolved",
        "impacted entities": "entities",
    }

    def metadata_table_to_report(self, report: IncidentReport, table_token):
        """Parse a table-like Paragraph token and update IncidentReport report."""
        md_table = {}
        for row_items in _table_to_rows(table_token):
            cells = _row_to_cells(row_items)
            if len(cells) < 3:
                continue

            label_text = _cell_text(cells[1]).lower().strip()

            field = None
            for key, val in self.METADATA_LABEL_TO_FIELD.items():
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
                        iim_url = extract_jira_iim_url(dest)
                        break
                    except NoJiraIIMURLError:
                        continue
                md_table[field] = iim_url or _cell_text(value_cell).strip()
            else:
                md_table[field] = _cell_text(value_cell)

        # Jira URL and key
        report.jira_url = extract_jira_iim_url(md_table.get("issues", ""))
        report.key = extract_jira_key(report.jira_url)

        # Status
        # incident report has "please select", "ongoing", "mitigated", "resolved"
        # Jira incident has "detected", "in progress", "mitigated", "resolved"
        status = md_table.get("status", "").strip()
        if status.lower().startswith("mitigated"):
            report.status = "Mitigated"
        elif status.lower().startswith(("resolved", "done")):
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

        # Impacted entities
        report.entities = normalize_entities(md_table.get("entities"))

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


class ReportParserPre20250520(ReportParser):
    TEMPLATE_VERSION = "pre-2025.05.20"

    METADATA_LABEL_TO_FIELD = {
        "incident severity": "severity",
        "jira ticket": "issues",
        "incident jira ticket": "issues",
        "issue detected via": "detection_method",
        "start of impact": "impact_start",
        "time of first impact": "impact_start",
        "time alerted": "alerted",
        "time acknowledge": "acknowledged",
        "time acknowledged": "acknowledged",
        "time responded/engaged": "responded",
        "time of repair": "mitigated",
        "time mitigated (repaired)": "mitigated",
        "time resolved": "resolved",
        "current status": "status",
    }

    def metadata_list_to_report(self, report: IncidentReport, list_token):
        """Parse the metadata bullet list and update IncidentReport."""
        if list_token is None:
            return

        md_data: dict = {}
        for item in list_token.children:
            item_text = get_text(item, keep_links=False)
            item_text_links = get_text(item, keep_links=True)

            if ":" not in item_text:
                continue

            label, _, value = item_text.partition(":")
            _, _, value_links = item_text_links.partition(":")

            label = label.strip().lower()

            field = None
            for key, val in self.METADATA_LABEL_TO_FIELD.items():
                if key in label:
                    field = val
                    break
            if field is None:
                continue

            if field == "issues":
                md_data[field] = value_links.strip()
            else:
                md_data[field] = value.strip()

        # Jira URL and key
        report.jira_url = extract_jira_iim_url(md_data.get("issues", ""))
        report.key = extract_jira_key(report.jira_url)

        # Status — old format may wrap in escaped brackets: \[Resolved\]
        status = re.sub(r"[\[\]\\]+", "", md_data.get("status", "")).strip()
        if status.lower().startswith("mitigated"):
            report.status = "Mitigated"
        elif status.lower().startswith(("resolved", "done")):
            report.status = "Resolved"
        else:
            report.status = "In Progress"

        # Severity
        severity = md_data.get("severity", "")
        if "S1" in severity:
            report.severity = "S1"
        elif "S2" in severity:
            report.severity = "S2"
        elif "S3" in severity:
            report.severity = "S3"
        elif "S4" in severity:
            report.severity = "S4"
        else:
            report.severity = None

        # Detection method
        detection = md_data.get("detection_method", "")
        if "Manual/Human" in detection or detection.lower() == "manual":
            report.detection_method = "Manual"
        elif "Automated" in detection:
            report.detection_method = "Automation"

        report.impact_start = extract_timestamp(md_data.get("impact_start"))
        report.alerted = extract_timestamp(md_data.get("alerted"))
        report.acknowledged = extract_timestamp(md_data.get("acknowledged"))
        report.responded = extract_timestamp(md_data.get("responded"))
        report.mitigated = extract_timestamp(md_data.get("mitigated"))
        report.resolved = extract_timestamp(md_data.get("resolved"))

    def _extract_action_item_status(self, cell_items):
        """Extract status string from action item ticket cell."""
        cell_text = _cell_text(cell_items)

        if "Status:" in cell_text:
            return cell_text.split("Status:", 1)[1].strip().upper()

        parts = []
        for item in cell_items:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, (marko.inline.RawText, marko.inline.Literal)):
                parts.append(item.children)
            elif isinstance(item, marko.inline.Link):
                pass  # skip link content
            elif hasattr(item, "children") and isinstance(item.children, list):
                parts.append(_cell_text(item.children))

        non_link_text = re.sub(r"[\[\]\s]+", " ", "".join(parts)).strip() or "unknown"
        return non_link_text.upper()

    def action_items_table_to_report(self, report: IncidentReport, table_token):
        """Parse action items table token and update IncidentReport report."""
        if table_token is None:
            return

        report.action_items = []
        for row_items in _table_to_rows(table_token):
            cells = _row_to_cells(row_items)
            if len(cells) < 3:
                continue

            ticket_cell = cells[1]
            ticket_text = _cell_text(ticket_cell).strip()

            title_cell = cells[2]
            title = _cell_text(title_cell).strip()
            if title:
                title = title.splitlines()[0]

            if not title and not ticket_text:
                continue
            if re.match(r"^[\s:\-]+$", ticket_text):
                continue
            if "jira ticket" in ticket_text.lower() or "ticket title" in title.lower():
                continue

            url = next(_cell_link_dests(ticket_cell), None)
            if url and url.startswith("mailto:"):
                continue
            if url == "https://mozilla-hub.atlassian.net/browse/":
                continue
            status = self._extract_action_item_status(ticket_cell)

            report.action_items.append(ActionItem(url=url, status=status, title=title))

    def action_items_list_to_report(self, report: IncidentReport, list_token):
        """Parse action items bullet list and update IncidentReport."""
        if list_token is None:
            return

        report.action_items = []
        for item in list_token.children:
            item_text = get_text(item, keep_links=False)

            # Determine status from checkbox prefix
            if re.match(r"^\[x\]", item_text, re.IGNORECASE):
                status = "DONE"
            else:
                status = "OPEN"

            # First non-mailto link is the action item URL
            url = next(
                (
                    dest
                    for dest in _recursive_link_dests(item)
                    if not dest.startswith("mailto:")
                ),
                None,
            )

            # Title: strip checkbox, optional leading ~~ (strikethrough), ticket ref
            title = item_text
            title = re.sub(r"^\[.\]\s*", "", title)
            title = re.sub(r"^~~", "", title)
            title = re.sub(r"^\[[^\]]*\]\s*", "", title)
            title = re.sub(r"~~$", "", title)
            # Strip trailing ticket reference like "(OBS-508)"
            title = re.sub(r"\s*\([A-Z]+-\d+\)\s*$", "", title)
            title = title.strip()

            if not title:
                continue

            report.action_items.append(ActionItem(url=url, status=status, title=title))

    def parse_markdown(self, report: IncidentReport, md: str):
        report.template_version = self.TEMPLATE_VERSION
        ast = marko.Markdown().parse(md)
        tokens = list(ast.children)

        metadata_list = None
        action_items_list = None
        action_items_table = None

        while tokens:
            token = tokens.pop(0)
            if is_header(token):
                header_text = get_text(token, keep_links=False)
                if "Incident: " in header_text or "Incident report: " in header_text:
                    report.summary = header_text.strip()[10:]
                    while tokens:
                        token = tokens.pop(0)
                        if isinstance(token, marko.block.List):
                            metadata_list = token
                            break

                if "action items" in header_text.lower():
                    while tokens:
                        token = tokens.pop(0)
                        if is_header(token):
                            tokens.insert(0, token)
                            break
                        elif isinstance(token, marko.block.List):
                            action_items_list = token
                            break
                        elif is_table(token):
                            action_items_table = token
                            break

        self.metadata_list_to_report(report, metadata_list)
        if action_items_list is not None:
            self.action_items_list_to_report(report, action_items_list)
        elif action_items_table is not None:
            self.action_items_table_to_report(report, action_items_table)
        return report


def parse_markdown(md):
    report = IncidentReport()

    if "Template version 2026.03.12" in md:
        parser = ReportParser20260312()
    elif "* **Incident Jira Ticket**" in md:
        parser = ReportParserPre20250520()
    else:
        parser = ReportParser20250520()

    report = parser.parse_markdown(report, md)
    return report
