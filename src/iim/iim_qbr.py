# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Computes stats for the IIM Jira project for incidents declared during the
specified quarter.
"""

import csv
from datetime import timedelta
import json
from importlib.resources import files as resources_files
import os
from typing import Optional

import arrow
import click
from dotenv import load_dotenv
import rich
from rich import box
from rich.table import Table

from iim.libjira import JiraAPI, fix_jira_incident_data
from iim.libstats import mean_timedelta, build_period_stats, humanize_timedelta


load_dotenv()


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


def tt_in_seconds(tt_value: Optional[timedelta]) -> Optional[float]:
    if tt_value is None:
        return tt_value

    return tt_value.total_seconds()


def count_reviewed(date_start, date_end, review_data, incident_keys=None):
    """Count unique incident keys reviewed in meetings within [date_start, date_end].

    If incident_keys is provided, only count keys that appear in that set.
    """
    reviewed = set()
    for review_date, keys in review_data.items():
        if date_start <= arrow.get(review_date) <= date_end:
            reviewed.update(keys)
    if incident_keys is not None:
        reviewed = reviewed & incident_keys
    return len(reviewed)


def s1s2_reviewed_pct(date_start, date_end, incidents, review_data):
    """Return % of S1/S2 incidents reviewed in meetings within [date_start, date_end]."""
    reviewed = set()
    for review_date, keys in review_data.items():
        if date_start <= arrow.get(review_date) <= date_end:
            reviewed.update(keys)
    s1s2 = [i for i in incidents if i.severity in ("S1", "S2")]
    if not s1s2:
        return 0.0
    return sum(1 for i in s1s2 if i.key in reviewed) / len(s1s2) * 100


def td_pct_change(a, b):
    """Return formatted pct change between two timedeltas, or '' if either is None."""
    if a is None or b is None:
        return ""
    a_s = a.total_seconds()
    if a_s == 0:
        return ""
    return f"{pct_change(a_s, b.total_seconds()):2.2f}%"


def build_table(quarter, rows, prev_quarter=None, fmt="table"):
    """
    Build a Rich Table from pre-computed row tuples.

    rows: list of (label, curr_str) when prev_quarter is None,
          or (label, prev_str, curr_str, pct_change_str) when prev_quarter is given.
    """
    table_box = box.MARKDOWN if fmt == "markdown" else None
    table = Table(box=table_box)
    if prev_quarter:
        table.add_column("key")
        table.add_column(prev_quarter)
        table.add_column(quarter)
        table.add_column("% change")
    else:
        table.add_column("key")
        table.add_column(quarter)
    for row in rows:
        table.add_row(*row)
    return table


@click.command()
@click.argument("quarter")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["table", "markdown"]),
    default="table",
    show_default=True,
    help="Output format.",
)
@click.pass_context
def iim_qbr(ctx, quarter, fmt):
    """
    Computes stats for the IIM Jira project for incidents declared in the
    specified quarter.

    QUARTER must be in YYYYqN form, e.g. 2025q4.

    See `README.md` for setup instructions.
    """
    quarter = quarter.strip()
    if "q" not in quarter:
        raise click.BadParameter("QUARTER must be in YYYYqN form, e.g. 2025q4")

    year_str, quarter_str = quarter.split("q")
    year = int(year_str)
    q = int(quarter_str)

    date_start, date_end = get_start_end(year, q)
    if q == 1:
        prev_year, prev_q = year - 1, 4
    else:
        prev_year, prev_q = year, q - 1
    prev_start, prev_end = get_start_end(prev_year, prev_q)
    prev_quarter = f"{prev_year}q{prev_q}"

    review_data = json.loads(
        (resources_files("iim") / "data" / "monthly_review_data.json").read_text()
    )

    jira_url = os.environ["JIRA_URL"].strip()
    username = os.environ["JIRA_USERNAME"].strip()
    token = os.environ["JIRA_TOKEN"].strip()

    jira_client = JiraAPI(base_url=jira_url, username=username, password=token)
    issue_data = jira_client.get_all_issues_for_project(project_key="IIM")

    incidents = [
        fix_jira_incident_data(jira_url=jira_url, incident=issue)
        for issue in issue_data
    ]

    def filter_by_range(incident_list, start, end):
        return [
            i
            for i in incident_list
            if i.declare_date and start <= arrow.get(i.declare_date) <= end
        ]

    def by_bucket(incident_list, bucket):
        return [i for i in incident_list if i.entities and i.entity_bucket == bucket]

    click.echo("Getting statistics...")

    these = filter_by_range(incidents, date_start, date_end)
    prev = filter_by_range(incidents, prev_start, prev_end)

    start_str = date_start.strftime("%Y-%m-%d")
    end_str = date_end.strftime("%Y-%m-%d")
    prev_start_str = prev_start.strftime("%Y-%m-%d")
    prev_end_str = prev_end.strftime("%Y-%m-%d")

    stats = build_period_stats(these, start_str, end_str)
    prev_stats = build_period_stats(prev, prev_start_str, prev_end_str)

    service_stats = build_period_stats(by_bucket(these, "service"), start_str, end_str)
    prev_service_stats = build_period_stats(
        by_bucket(prev, "service"), prev_start_str, prev_end_str
    )

    product_stats = build_period_stats(by_bucket(these, "product"), start_str, end_str)
    prev_product_stats = build_period_stats(
        by_bucket(prev, "product"), prev_start_str, prev_end_str
    )

    click.echo()
    click.echo(f"QBR metrics {quarter}: {start_str} to {end_str}")
    click.echo()

    with open(f"qbr_stats_{quarter}.csv", "w") as fp:
        writer = csv.writer(fp)
        writer.writerow(
            [
                "key",
                "jira_url",
                "report_url",
                "report_modified",
                "summary",
                "status",
                "entity_bucket",
                "entities",
                "severity",
                "detection_method",
                "impact_start",
                "declared",
                "tt-declared",
                "alerted",
                "tt-alerted",
                "responded",
                "tt-responded",
                "mitigated",
                "tt-mitigated",
                "resolved",
                "tt-resolved",
            ]
        )
        for incident in these:
            writer.writerow(
                [
                    incident.key,
                    incident.jira_url,
                    incident.report_url,
                    incident.report_modified,
                    incident.summary,
                    incident.status,
                    incident.entity_bucket,
                    incident.entities,
                    incident.severity,
                    incident.detection_method,
                    incident.impact_start,
                    incident.declared,
                    tt_in_seconds(incident.tt_declared),
                    # degrade to detected for older reports
                    incident.alerted or incident.detected,
                    tt_in_seconds(incident.tt_alerted),
                    incident.responded,
                    tt_in_seconds(incident.tt_responded),
                    incident.mitigated,
                    tt_in_seconds(incident.tt_mitigated),
                    incident.resolved,
                    tt_in_seconds(incident.tt_resolved),
                ]
            )

    curr_svc_keys = {i.key for i in by_bucket(these, "service")}
    prev_svc_keys = {i.key for i in by_bucket(prev, "service")}
    curr_reviewed = count_reviewed(date_start, date_end, review_data, curr_svc_keys)
    prev_reviewed = count_reviewed(prev_start, prev_end, review_data, prev_svc_keys)
    curr_s1s2_pct = s1s2_reviewed_pct(
        date_start, date_end, by_bucket(these, "service"), review_data
    )
    prev_s1s2_pct = s1s2_reviewed_pct(
        prev_start, prev_end, by_bucket(prev, "service"), review_data
    )

    def auto_pct(incident_list):
        known = [
            i for i in incident_list if i.detection_method in ("Manual", "Automation")
        ]
        if not known:
            return 0.0
        return (
            sum(1 for i in known if i.detection_method == "Automation")
            / len(known)
            * 100
        )

    all_auto_prev = auto_pct(by_bucket(prev, "service"))
    all_auto_curr = auto_pct(by_bucket(these, "service"))
    all_mtt_alerted_prev = mean_timedelta([i.tt_alerted for i in prev])
    all_mtt_alerted_curr = mean_timedelta([i.tt_alerted for i in these])
    all_mtt_responded_prev = mean_timedelta([i.tt_responded for i in prev])
    all_mtt_responded_curr = mean_timedelta([i.tt_responded for i in these])
    all_mtt_mitigated_prev = mean_timedelta([i.tt_mitigated for i in prev])
    all_mtt_mitigated_curr = mean_timedelta([i.tt_mitigated for i in these])

    svc_auto_prev = prev_service_stats.service_detection_method_counts.get(
        "Automation", 0.0
    )
    svc_auto_curr = service_stats.service_detection_method_counts.get("Automation", 0.0)
    prod_auto_prev = prev_product_stats.product_detection_method_counts.get(
        "Automation", 0.0
    )
    prod_auto_curr = product_stats.product_detection_method_counts.get(
        "Automation", 0.0
    )
    prod_manual_prev = prev_product_stats.product_detection_method_counts.get(
        "Manual", 0.0
    )
    prod_manual_curr = product_stats.product_detection_method_counts.get("Manual", 0.0)

    rows = [
        (
            "Total incidents",
            str(prev_stats.total_incidents),
            str(stats.total_incidents),
            f"{pct_change(prev_stats.total_incidents, stats.total_incidents):2.2f}%",
        ),
        (
            "Total incidents (services)",
            str(prev_service_stats.total_incidents),
            str(service_stats.total_incidents),
            f"{pct_change(prev_service_stats.total_incidents, service_stats.total_incidents):2.2f}%",
        ),
        (
            "Number of incidents reviewed (services)",
            str(prev_reviewed),
            str(curr_reviewed),
            f"{pct_change(prev_reviewed, curr_reviewed):2.2f}%",
        ),
        (
            "Percent S1/S2 incidents reviewed (services)",
            f"{prev_s1s2_pct:2.2f}%",
            f"{curr_s1s2_pct:2.2f}%",
            f"{pct_change(prev_s1s2_pct, curr_s1s2_pct):2.2f}%",
        ),
        (
            "Number of impacted entities (services)",
            str(prev_service_stats.total_entities),
            str(service_stats.total_entities),
            f"{pct_change(prev_service_stats.total_entities, service_stats.total_entities):2.2f}%",
        ),
        *(
            (
                f"Severity: {sev} (services)",
                f"{prev_service_stats.severity_counts[sev]:2.0f}%",
                f"{service_stats.severity_counts[sev]:2.0f}%",
                f"{pct_change(prev_service_stats.severity_counts[sev], service_stats.severity_counts[sev]):2.2f}%",
            )
            for sev in ("S1", "S2", "S3", "S4")
        ),
        (
            "Detection: automation (services)",
            f"{all_auto_prev:2.2f}%",
            f"{all_auto_curr:2.2f}%",
            f"{pct_change(all_auto_prev, all_auto_curr):2.2f}%",
        ),
        (
            "MTT alerted (services)",
            humanize_timedelta(prev_service_stats.service_mean_tt_alert),
            humanize_timedelta(service_stats.service_mean_tt_alert),
            td_pct_change(
                prev_service_stats.service_mean_tt_alert,
                service_stats.service_mean_tt_alert,
            ),
        ),
        (
            "MTT responded (services)",
            humanize_timedelta(prev_service_stats.service_mean_tt_resp),
            humanize_timedelta(service_stats.service_mean_tt_resp),
            td_pct_change(
                prev_service_stats.service_mean_tt_resp,
                service_stats.service_mean_tt_resp,
            ),
        ),
        (
            "MTT mitigated (services)",
            humanize_timedelta(prev_service_stats.service_mean_tt_mit),
            humanize_timedelta(service_stats.service_mean_tt_mit),
            td_pct_change(
                prev_service_stats.service_mean_tt_mit,
                service_stats.service_mean_tt_mit,
            ),
        ),
        ([]),
        (
            "MTT alerted",
            humanize_timedelta(all_mtt_alerted_prev),
            humanize_timedelta(all_mtt_alerted_curr),
            td_pct_change(all_mtt_alerted_prev, all_mtt_alerted_curr),
        ),
        (
            "MTT responded",
            humanize_timedelta(all_mtt_responded_prev),
            humanize_timedelta(all_mtt_responded_curr),
            td_pct_change(all_mtt_responded_prev, all_mtt_responded_curr),
        ),
        (
            "MTT mitigated",
            humanize_timedelta(all_mtt_mitigated_prev),
            humanize_timedelta(all_mtt_mitigated_curr),
            td_pct_change(all_mtt_mitigated_prev, all_mtt_mitigated_curr),
        ),
        (
            "Service: total incidents",
            str(prev_service_stats.total_incidents),
            str(service_stats.total_incidents),
            f"{pct_change(prev_service_stats.total_incidents, service_stats.total_incidents):2.2f}%",
        ),
        (
            "Service: detection automation",
            f"{svc_auto_prev:2.2f}%",
            f"{svc_auto_curr:2.2f}%",
            f"{pct_change(svc_auto_prev, svc_auto_curr):2.2f}%",
        ),
        (
            "Service: MTT alerted",
            humanize_timedelta(prev_service_stats.service_mean_tt_alert),
            humanize_timedelta(service_stats.service_mean_tt_alert),
            td_pct_change(
                prev_service_stats.service_mean_tt_alert,
                service_stats.service_mean_tt_alert,
            ),
        ),
        (
            "Service: MTT mitigated",
            humanize_timedelta(prev_service_stats.service_mean_tt_mit),
            humanize_timedelta(service_stats.service_mean_tt_mit),
            td_pct_change(
                prev_service_stats.service_mean_tt_mit,
                service_stats.service_mean_tt_mit,
            ),
        ),
        (
            "Product: total incidents",
            str(prev_product_stats.total_incidents),
            str(product_stats.total_incidents),
            f"{pct_change(prev_product_stats.total_incidents, product_stats.total_incidents):2.2f}%",
        ),
        (
            "Product: detection automation",
            f"{prod_auto_prev:2.2f}%",
            f"{prod_auto_curr:2.2f}%",
            f"{pct_change(prod_auto_prev, prod_auto_curr):2.2f}%",
        ),
        (
            "Product: detection manual",
            f"{prod_manual_prev:2.2f}%",
            f"{prod_manual_curr:2.2f}%",
            f"{pct_change(prod_manual_prev, prod_manual_curr):2.2f}%",
        ),
        (
            "Product: MTT alerted",
            humanize_timedelta(prev_product_stats.product_mean_tt_alert),
            humanize_timedelta(product_stats.product_mean_tt_alert),
            td_pct_change(
                prev_product_stats.product_mean_tt_alert,
                product_stats.product_mean_tt_alert,
            ),
        ),
        (
            "Product: MTT mitigated",
            humanize_timedelta(prev_product_stats.product_mean_tt_mit),
            humanize_timedelta(product_stats.product_mean_tt_mit),
            td_pct_change(
                prev_product_stats.product_mean_tt_mit,
                product_stats.product_mean_tt_mit,
            ),
        ),
    ]
    rich.print(build_table(quarter, rows, prev_quarter, fmt))
