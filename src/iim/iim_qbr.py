# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Computes stats for the IIM Jira project for incidents declared during the
specified quarter.
"""

import csv
import dataclasses
import os
import statistics

import arrow
import click
from dotenv import load_dotenv
import rich
from rich.table import Table

from iim.libjira import JiraAPI, fix_jira_incident_data


load_dotenv()


def humanize(total_minutes: int) -> str:
    sign = "-" if total_minutes < 0 else ""
    total_seconds = int(abs(total_minutes) * 60)

    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{days:,}d")
    if hours:
        parts.append(f"{hours:,}h")
    if minutes:
        parts.append(f"{minutes:,}m")
    if seconds or not parts:
        parts.append(f"{seconds:,}s")

    # Only take the two most significant parts
    parts = parts[:2]

    return sign + " ".join(parts)


@dataclasses.dataclass
class Stats:
    total: int = 0
    severity_breakdown: dict = dataclasses.field(default_factory=dict)
    detection_breakdown: dict = dataclasses.field(default_factory=dict)
    tt_alerted: list[int] = dataclasses.field(default_factory=list)
    tt_responded: list[int] = dataclasses.field(default_factory=list)
    tt_mitigated: list[int] = dataclasses.field(default_factory=list)
    entities: set = dataclasses.field(default_factory=set)
    number_reviewed: int = 0
    s1s2_reviewed: int = 0

    @property
    def s1s2_reviewed_pct(self):
        total = len(self.severity_breakdown.get("S1", [])) + len(self.severity_breakdown.get("S2", []))
        return self.s1s2_reviewed / total * 100

    @property
    def automation(self):
        return len(self.detection_breakdown.get("Automation", []))

    @property
    def automation_pct(self):
        return self.automation / self.total * 100

    @property
    def manual(self):
        return len(self.detection_breakdown.get("Manual", []))

    @property
    def manual_pct(self):
        return self.manual / self.total * 100

    @property
    def s1(self):
        return len(self.severity_breakdown.get("S1", []))

    @property
    def s1_pct(self):
        return self.s1 / self.total * 100

    @property
    def s2(self):
        return len(self.severity_breakdown.get("S2", []))

    @property
    def s2_pct(self):
        return self.s2 / self.total * 100

    @property
    def s3(self):
        return len(self.severity_breakdown.get("S3", []))

    @property
    def s3_pct(self):
        return self.s3 / self.total * 100

    @property
    def s4(self):
        return len(self.severity_breakdown.get("S4", []))

    @property
    def s4_pct(self):
        return self.s4 / self.total * 100

    @property
    def mtt_alerted(self):
        return statistics.mean(self.tt_alerted)

    @property
    def mtt_responded(self):
        return statistics.mean(self.tt_responded)

    @property
    def mtt_mitigated(self):
        return statistics.mean(self.tt_mitigated)


def get_stats(incidents):
    stats = Stats()

    stats.total = len(incidents)

    for incident in incidents:
        # Drop items with no impact_start
        if incident.impact_start is None:
            continue

        impact_start = arrow.get(incident.impact_start)

        # Drop extreme response times
        if incident.responded and (arrow.get(incident.responded) - impact_start).total_seconds() > 1800000:
            click.echo(f"Error: {incident.key} {incident.summary!r} has excessive response time: {arrow.get(incident.responded) - impact_start}")
            continue

        stats.severity_breakdown.setdefault(incident.severity, []).append(incident)
        stats.detection_breakdown.setdefault(incident.detection_method, []).append(incident)
        alerted = incident.alerted or incident.detected
        if alerted is not None:
            stats.tt_alerted.append((arrow.get(alerted) - impact_start).total_seconds() / 60)

        if incident.responded is not None:
            stats.tt_responded.append((arrow.get(incident.responded) - impact_start).total_seconds() / 60)

        if incident.mitigated is not None:
            stats.tt_mitigated.append((arrow.get(incident.mitigated) - impact_start).total_seconds() / 60)

        if incident.entities:
            stats.entities.update([entity.lower().strip() for entity in incident.entities.split(", ")])

    stats.number_reviewed = int(click.prompt("Number reviewed?: ").strip())
    stats.s1s2_reviewed = int(click.prompt("Number S1/S2 reviewed?: ").strip())
    stats.s1s2_incidents = len(stats.severity_breakdown.get("S1", [])) + len(stats.severity_breakdown.get("S2", []))

    return stats


def get_start_end(year, quarter):
    if quarter == 1:
        date_start = arrow.get(f"{year}-01-01 00:00:00")
        date_end = arrow.get(f"{year}-03-31 23:59:59")
    elif quarter == 2:
        date_start = arrow.get(f"{year}-04-01 00:00:00")
        date_end = arrow.get(f"{year}-06-30 23:59:59")
    elif quarter == 3:
        date_start = arrow.get(f"{year}-07-01 00:00:00")
        date_end = arrow.get(f"{year}-09-30 23:59:59")
    elif quarter == 4:
        date_start = arrow.get(f"{year}-10-01 00:00:00")
        date_end = arrow.get(f"{year}-12-31 23:59:59")
    else:
        raise ValueError("quarter must be 1, 2, 3, or 4")
    return date_start, date_end


def pct_change(a, b):
    if a == 0:
        return -1

    return (b - a) / a * 100


@click.command()
@click.argument("period")
@click.pass_context
def iim_qbr(ctx, period):
    """
    Computes stats for the IIM Jira project for incidents declared in the
    specified quarter.

    PERIOD can be one of:

    \b
    * "all" for all data
    * "YYYY" for all the data in a specific year
    * "YYYYqN" for all the data in a specific year and quarter

    Create an API token in Jira and set these in the `.env` file:

    \b
    * JIRA_USERNAME
    * JIRA_TOKEN
    * JIRA_URL
    """

    date_start = date_end = None
    previous_start = previous_end = None
    previous_period = None

    period = period.strip()
    if period == "all":
        pass

    elif "q" in period:
        year, quarter = period.split("q")
        year = int(year)
        quarter = int(quarter)

        date_start, date_end = get_start_end(year, quarter)
        if quarter == 1:
            previous_year = year - 1
            previous_quarter = 4
        else:
            previous_year = year
            previous_quarter = quarter - 1
        previous_start, previous_end = get_start_end(previous_year, previous_quarter)
        previous_period = f"{previous_year}q{previous_quarter}"

    else:
        year = period
        date_start = arrow.get(f"{year}-01-01 00:00:00")
        date_end = arrow.get(f"{year}-12-31 23:59:59")

    jira_url = os.environ["JIRA_URL"].strip()
    username = os.environ["JIRA_USERNAME"].strip()
    token = os.environ["JIRA_TOKEN"].strip()

    jira_client = JiraAPI(base_url=jira_url, username=username, password=token)
    issue_data = jira_client.get_all_issues_for_project(project_key="IIM")

    incidents = [
        fix_jira_incident_data(jira_url=jira_url, incident=issue)
        for issue in issue_data
    ]

    if period != "all":
        previous_incidents = [
            incident for incident in incidents
            if incident.declare_date and previous_start <= arrow.get(incident.declare_date) <= previous_end
        ]
        incidents = [
            incident for incident in incidents
            if incident.declare_date and date_start <= arrow.get(incident.declare_date) <= date_end
        ]

    click.echo("Determining statistics data...")

    click.echo("Getting statistics...")
    stats = get_stats(incidents)

    if previous_start:
        click.echo("Getting statistics for previous period...")
        previous_stats = get_stats(previous_incidents)

    click.echo()

    if period == "all":
        click.echo("Looking at: all data")
    else:
        click.echo(f"Looking at: {date_start.strftime('%Y-%m-%d')} to {date_end.strftime('%Y-%m-%d')}")

    click.echo()

    table = Table()

    with open(f"qbr_stats_{period}.csv", "w") as fp:
        writer = csv.writer(fp)
        for incident in incidents:
            writer.writerow(
                [
                    incident.key,
                    incident.entities,
                    incident.impact_start,
                    incident.severity,
                    incident.detection_method,
                    incident.alerted or incident.detected,
                    incident.responded,
                    incident.mitigated,
                ]
            )

    if previous_start:
        table.add_column("key")
        table.add_column(previous_period)
        table.add_column(period)
        table.add_column("% change")

        table.add_row(
            "Total incidents",
            str(previous_stats.total),
            str(stats.total),
            f"{pct_change(previous_stats.total, stats.total):2.2f}%"
        )

        table.add_row(
            "Severity: S1",
            f"{previous_stats.s1:<3}  {previous_stats.s1_pct:2.2f}%",
            f"{stats.s1:<3}  {stats.s1_pct:2.2f}%",
            f"{pct_change(previous_stats.s1, stats.s1):2.2f}%"
        )
        table.add_row(
            "Severity: S2",
            f"{previous_stats.s2:<3}  {previous_stats.s2_pct:2.2f}%",
            f"{stats.s2:<3}  {stats.s2_pct:2.2f}%",
            f"{pct_change(previous_stats.s2, stats.s2):2.2f}%"
        )
        table.add_row(
            "Severity: S3",
            f"{previous_stats.s3:<3}  {previous_stats.s3_pct:2.2f}%",
            f"{stats.s3:<3}  {stats.s3_pct:2.2f}%",
            f"{pct_change(previous_stats.s3, stats.s3):2.2f}%"
        )
        table.add_row(
            "Severity: S4",
            f"{previous_stats.s4:<3}  {previous_stats.s4_pct:2.2f}%",
            f"{stats.s4:<3}  {stats.s4_pct:2.2f}%",
            f"{pct_change(previous_stats.s4, stats.s4):2.2f}%"
        )

        table.add_row(
            "Number reviewed",
            str(previous_stats.number_reviewed),
            str(stats.number_reviewed),
            f"{pct_change(previous_stats.number_reviewed, stats.number_reviewed):2.2f}%",
        )
        table.add_row(
            "Percent S1/S2 reviewed",
            f"{previous_stats.s1s2_reviewed_pct:2.2f}%",
            f"{stats.s1s2_reviewed_pct:2.2f}%",
            f"{pct_change(previous_stats.s1s2_reviewed_pct, stats.s1s2_reviewed_pct):2.2f}%"
            ""
        )
        table.add_row(
            "Impacted entities",
            str(len(previous_stats.entities)),
            str(len(stats.entities)),
            f"{pct_change(len(previous_stats.entities), len(stats.entities)):2.2f}%"
        )

        table.add_row(
            "Detection by automation",
            f"{previous_stats.automation} ({previous_stats.automation_pct:2.2f}%)",
            f"{stats.automation} ({stats.automation_pct:2.2f}%)",
            f"{pct_change(previous_stats.automation, stats.automation):2.2f}%",
        )
        table.add_row(
            "Detection by manual",
            f"{previous_stats.manual} ({previous_stats.manual_pct:2.2f}%)",
            f"{stats.manual} ({stats.manual_pct:2.2f}%)",
            f"{pct_change(previous_stats.manual, stats.manual):2.2f}%",
        )

        table.add_row(
            "MTT alerted",
            humanize(previous_stats.mtt_alerted),
            humanize(stats.mtt_alerted),
            f"{pct_change(previous_stats.mtt_alerted, stats.mtt_alerted):2.2f}%",
        )
        table.add_row(
            "MTT responded",
            humanize(previous_stats.mtt_responded),
            humanize(stats.mtt_responded),
            f"{pct_change(previous_stats.mtt_responded, stats.mtt_responded):2.2f}%",
        )
        table.add_row(
            "MTT mitigated",
            humanize(previous_stats.mtt_mitigated),
            humanize(stats.mtt_mitigated),
            f"{pct_change(previous_stats.mtt_mitigated, stats.mtt_mitigated):2.2f}%",
        )

    else:
        table.add_column("key")
        table.add_column(period)

        table.add_row("Total incidents", str(stats.total))
        table.add_row("Severity: S1", f"{stats.s1:<3}  {stats.s1_pct:2.2f}%")
        table.add_row("Severity: S2", f"{stats.s2:<3}  {stats.s2_pct:2.2f}%")
        table.add_row("Severity: S3", f"{stats.s3:<3}  {stats.s3_pct:2.2f}%")
        table.add_row("Severity: S4", f"{stats.s4:<3}  {stats.s4_pct:2.2f}%")
        table.add_row("Number reviewed", str(stats.number_reviewed))
        table.add_row("Percent S1/S2 reviewed", f"{(stats.s1s2_reviewed / stats.s1s2_incidents) * 100:2.2f}%")
        table.add_row("Impacted entities", str(len(stats.entities)))
        table.add_row("Detection by automation", f"{stats.automation} ({stats.automation_pct:2.2f}%)")
        table.add_row("Detection by manual", f"{stats.manual} ({stats.manual_pct:2.2f}%)")

        table.add_row("MTT alerted", humanize(stats.mtt_alerted))
        table.add_row("MTT responded", humanize(stats.mtt_responded))
        table.add_row("MTT mitigated", humanize(stats.mtt_mitigated))

    rich.print(table)
