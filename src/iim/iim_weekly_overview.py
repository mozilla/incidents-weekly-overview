# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Computes a weekly report for incidents.
"""

import os
from collections import Counter
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Optional, cast

import arrow
import click
import css_inline
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from iim.libjira import (
    JiraAPI,
    fix_jira_incident_data,
    generate_jira_link,
)


OVERVIEWS_DIR = "incident_overviews"


load_dotenv()


def friendly_date(date_str: str) -> str:
    """Convert YYYY-MM-DD to 'Month D, YYYY' format."""
    dt = arrow.get(date_str)
    return dt.format("MMMM D, YYYY")


def humanize_timedelta(td: Optional[timedelta]) -> str:
    if td is None:
        return "?"

    total_seconds = int(td.total_seconds())
    sign = "-" if total_seconds < 0 else ""
    total_seconds = abs(total_seconds)

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


@dataclass
class PeriodStats:
    start: str  # YYYY-MM-DD, inclusive
    end: str  # YYYY-MM-DD, exclusive
    total_incidents: int
    total_entities: int  # distinct entity names (excluding unknown/None)
    top_entities: list[tuple[str, int]]  # top 5, descending by count
    severity_counts: dict[str, float]  # {"S1": %, "S2": %, "S3": %, "S4": %} as 0-100
    status_counts: dict[
        str, float
    ]  # {"Detected": %, "InProgress": %, "Mitigated": %, "Resolved": %} as 0-100
    service_mean_tt_dec: Optional[timedelta]
    service_mean_tt_alert: Optional[timedelta]
    service_mean_tt_mit: Optional[timedelta]
    service_mean_tt_res: Optional[timedelta]
    product_mean_tt_dec: Optional[timedelta]
    product_mean_tt_alert: Optional[timedelta]
    product_mean_tt_mit: Optional[timedelta]
    product_mean_tt_res: Optional[timedelta]
    mean_action_items: Optional[
        float
    ]  # mean per resolved incident with action_items set


@dataclass
class TrendsSummary:
    recent: PeriodStats
    prior: PeriodStats


def _mean_timedelta(values: list[Optional[timedelta]]) -> Optional[timedelta]:
    filtered = [v for v in values if v is not None]
    if not filtered:
        return None
    return sum(filtered, timedelta()) / len(filtered)


def direction(prior_val, recent_val) -> str:
    if prior_val is None or recent_val is None:
        return "same"
    if isinstance(prior_val, timedelta):
        prior_val = prior_val.total_seconds()
        recent_val = recent_val.total_seconds()
    if recent_val > prior_val:
        return "up"
    if recent_val < prior_val:
        return "down"
    return "same"


def direction_symbol(
    prior_val,
    recent_val,
    up_is_good: bool = False,
    up_label: str = "higher",
    down_label: str = "lower",
) -> Markup:
    d = direction(prior_val, recent_val)
    if d == "same":
        return Markup('<span style="color: #6B7280;">same</span>')
    if d == "up":
        color = "#1B991B" if up_is_good else "#991B1B"
        return Markup(
            f'<span style="color: {color}; font-weight: bold;">&#9650; {up_label}</span>'
        )
    # down
    color = "#991B1B" if up_is_good else "#1B991B"
    return Markup(
        f'<span style="color: {color}; font-weight: bold;">&#9660; {down_label}</span>'
    )


def _build_period_stats(incidents, start: str, end: str) -> PeriodStats:
    # top entities
    entity_counter: Counter = Counter()
    for incident in incidents:
        if not incident.entities:
            continue
        for entity in incident.entities.split(","):
            entity = entity.strip()
            if entity and entity != "unknown":
                entity_counter[entity] += 1
    total_entities = len(entity_counter)
    top_entities = sorted(entity_counter.items(), key=lambda x: (-x[1], x[0]))[:5]

    # severity percentages
    total = len(incidents)
    sev_raw = {"S1": 0, "S2": 0, "S3": 0, "S4": 0}
    for incident in incidents:
        if incident.severity in sev_raw:
            sev_raw[incident.severity] += 1
    severity_counts = {
        k: (v / total * 100) if total else 0.0 for k, v in sev_raw.items()
    }

    # status percentages
    status_raw = {"Detected": 0, "InProgress": 0, "Mitigated": 0, "Resolved": 0}
    for incident in incidents:
        if incident.status in status_raw:
            status_raw[incident.status] += 1
    status_counts = {
        k: (v / total * 100) if total else 0.0 for k, v in status_raw.items()
    }

    # TT means by entity_bucket
    service = [i for i in incidents if i.entity_bucket == "service"]
    product = [i for i in incidents if i.entity_bucket == "product"]
    service_resolved = [i for i in service if i.status == "Resolved"]
    product_resolved = [i for i in product if i.status == "Resolved"]

    resolved_with_ais = [
        i for i in incidents if i.status == "Resolved" and i.action_items is not None
    ]
    if resolved_with_ais:
        mean_action_items: Optional[float] = sum(
            len(i.action_items) for i in resolved_with_ais
        ) / len(resolved_with_ais)
    else:
        mean_action_items = None

    return PeriodStats(
        start=start,
        end=end,
        total_incidents=len(incidents),
        total_entities=total_entities,
        top_entities=top_entities,
        severity_counts=severity_counts,
        status_counts=status_counts,
        mean_action_items=mean_action_items,
        service_mean_tt_dec=_mean_timedelta([i.tt_declared for i in service]),
        service_mean_tt_alert=_mean_timedelta([i.tt_alerted for i in service]),
        service_mean_tt_mit=_mean_timedelta([i.tt_mitigated for i in service]),
        service_mean_tt_res=_mean_timedelta([i.tt_resolved for i in service_resolved]),
        product_mean_tt_dec=_mean_timedelta([i.tt_declared for i in product]),
        product_mean_tt_alert=_mean_timedelta([i.tt_alerted for i in product]),
        product_mean_tt_mit=_mean_timedelta([i.tt_mitigated for i in product]),
        product_mean_tt_res=_mean_timedelta([i.tt_resolved for i in product_resolved]),
    )


def compute_trends_summary(incidents, this_friday: str) -> TrendsSummary:
    recent_start = arrow.get(this_friday).shift(weeks=-6).format("YYYY-MM-DD")
    prior_start = arrow.get(this_friday).shift(weeks=-12).format("YYYY-MM-DD")

    recent_incidents = [
        i
        for i in incidents
        if i.declare_date and recent_start <= i.declare_date < this_friday
    ]
    prior_incidents = [
        i
        for i in incidents
        if i.declare_date and prior_start <= i.declare_date < recent_start
    ]

    return TrendsSummary(
        recent=_build_period_stats(recent_incidents, recent_start, this_friday),
        prior=_build_period_stats(prior_incidents, prior_start, recent_start),
    )


@click.command()
@click.pass_context
def iim_weekly_report(ctx):
    """
    Computes a weekly report based on Jira data. Make sure to update the data
    in Jira before running this report.

    See `README.md` for setup instructions.
    """
    jira_client = JiraAPI(
        base_url=os.environ["JIRA_URL"].strip(),
        username=os.environ["JIRA_USERNAME"].strip(),
        password=os.environ["JIRA_TOKEN"].strip(),
    )

    if not os.path.exists(OVERVIEWS_DIR):
        os.mkdir(OVERVIEWS_DIR)

    issue_data = jira_client.get_all_issues_for_project(project_key="IIM")

    incidents = [
        fix_jira_incident_data(jira_url=jira_client.base_url, incident=incident)
        for incident in issue_data
    ]

    # shift to last week, floor('week') gets monday, shift 4 days to friday
    last_friday = (
        arrow.now().shift(weeks=-1).floor("week").shift(days=4).format("YYYY-MM-DD")
    )
    this_friday = arrow.now().floor("week").shift(days=4).format("YYYY-MM-DD")

    click.echo(f"From: {last_friday} to {this_friday}")
    new_incidents = [
        incident
        for incident in incidents
        if (
            incident.declare_date is not None
            and incident.declare_date[0:11] >= last_friday
            and incident.declare_date[0:11] <= this_friday
        )
    ]

    severity_breakdown = {}
    for item in new_incidents:
        severity_breakdown[item.severity] = severity_breakdown.get(item.severity, 0) + 1

    three_months_ago = arrow.now().shift(months=-3).format("YYYY-MM-DD")
    active_incidents = [
        incident
        for incident in incidents
        if (
            incident.status != "Resolved"
            and incident.declare_date is not None
            and incident.declare_date >= three_months_ago
        )
    ]
    dormant_incidents = [
        incident
        for incident in incidents
        if (
            incident.status != "Resolved"
            and (
                incident.declare_date is None
                or incident.declare_date < three_months_ago
            )
        )
    ]

    four_weeks_ago = arrow.now().shift(weeks=-4).format("YYYY-MM-DD")
    recently_resolved = [
        incident
        for incident in incidents
        if (
            incident.status == "Resolved"
            and incident.resolved is not None
            and incident.resolved[:10] >= four_weeks_ago
        )
    ]

    trends_summary = compute_trends_summary(incidents, this_friday)

    env = Environment(
        loader=FileSystemLoader("templates"), autoescape=select_autoescape()
    )
    env.filters["humanize_timedelta"] = humanize_timedelta
    env.filters["friendly_date"] = friendly_date
    env.globals["direction_symbol"] = cast(Any, direction_symbol)

    template = env.get_template("incident_overview.html")
    html = template.render(
        title=f"Weekly Incident Overview: {friendly_date(this_friday)}",
        this_friday=this_friday,
        last_friday=last_friday,
        num_incidents=len(new_incidents),
        num_s1_incidents=severity_breakdown.get("S1", 0),
        num_s2_incidents=severity_breakdown.get("S2", 0),
        num_s3_incidents=severity_breakdown.get("S3", 0),
        num_s4_incidents=severity_breakdown.get("S4", 0),
        new_incidents=new_incidents,
        new_incidents_link=generate_jira_link(
            jira_url=jira_client.base_url,
            incident_keys=[item.key for item in new_incidents if item.key],
        ),
        active_incidents=active_incidents,
        active_incidents_link=generate_jira_link(
            jira_url=jira_client.base_url,
            incident_keys=[item.key for item in active_incidents if item.key],
        ),
        dormant_incidents=dormant_incidents,
        dormant_incidents_link=generate_jira_link(
            jira_url=jira_client.base_url,
            incident_keys=[item.key for item in dormant_incidents if item.key],
        ),
        recently_resolved=recently_resolved,
        recently_resolved_link=generate_jira_link(
            jira_url=jira_client.base_url,
            incident_keys=[item.key for item in recently_resolved if item.key],
        ),
        trends_summary=trends_summary,
    )
    inliner = css_inline.CSSInliner()
    fixed_html = inliner.inline(html)

    # NOTE(willkg): arrow only does YYYY-MM-DD. we can't get it to do YYYYMMDD
    # or YYYY_MM_DD. it's unclear why.
    file_friendly_date = this_friday.format("YYYY-MM-DD").replace("-", "")
    fn = os.path.join(OVERVIEWS_DIR, f"incident_overview_{file_friendly_date}.html")
    with open(fn, "w") as fp:
        fp.write(fixed_html)

    click.echo(f"Report written to: {fn}")
