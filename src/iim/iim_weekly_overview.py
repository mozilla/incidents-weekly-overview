# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Computes a weekly report for incidents.
"""

import os
from typing import Any, cast

import arrow
import click
import css_inline
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, select_autoescape

from iim.libjira import (
    JiraAPI,
    fix_jira_incident_data,
    generate_jira_date_range_link,
    generate_jira_link,
)
from iim.libstats import (
    compute_period_comparison,
    direction_symbol,
    format_pvar,
    humanize_timedelta,
)


OVERVIEWS_DIR = "incident_overviews"


load_dotenv()


def split_entities(entities: str | None) -> list[str]:
    if entities is None:
        return []
    return entities.split(",")


def friendly_date(date_str: str) -> str:
    """Convert YYYY-MM-DD to 'Month D, YYYY' format."""
    dt = arrow.get(date_str)
    return dt.format("MMMM D, YYYY")


@click.command()
@click.pass_context
@click.option(
    "--friday",
    "friday_date",
    default=None,
    metavar="YYYY-MM-DD",
    help="Friday date to generate report for. Defaults to this week's Friday.",
)
def iim_weekly_report(ctx, friday_date):
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
    if not incidents:
        click.echo(
            "No incidents were fetched. Check your API token to see if it has "
            "expired. If so, create a new one.",
            err=True,
        )
        ctx.exit(1)

    # shift to last week, floor('week') gets monday, shift 4 days to friday
    if friday_date:
        this_friday = friday_date
    else:
        this_friday = arrow.now().floor("week").shift(days=4).format("YYYY-MM-DD")
    last_friday = arrow.get(this_friday).shift(weeks=-1).format("YYYY-MM-DD")

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

    current_start = arrow.get(this_friday).shift(weeks=-6).format("YYYY-MM-DD")
    prior_start = arrow.get(this_friday).shift(weeks=-12).format("YYYY-MM-DD")
    trends_summary = compute_period_comparison(
        incidents, current_start, this_friday, prior_start, current_start
    )

    env = Environment(
        loader=FileSystemLoader("templates"), autoescape=select_autoescape()
    )
    env.filters["humanize_timedelta"] = humanize_timedelta
    env.filters["friendly_date"] = friendly_date
    env.filters["split_entities"] = split_entities
    env.globals["direction_symbol"] = cast(Any, direction_symbol)
    env.globals["format_pvar"] = cast(Any, format_pvar)

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
        prior_trends_link=generate_jira_date_range_link(
            jira_url=jira_client.base_url,
            start_date=prior_start,
            end_date=current_start,
        ),
        recent_trends_link=generate_jira_date_range_link(
            jira_url=jira_client.base_url,
            start_date=current_start,
            end_date=this_friday,
        ),
    )
    inliner = css_inline.CSSInliner()
    fixed_html = inliner.inline(html)

    # NOTE(willkg): arrow only does YYYY-MM-DD. we can't get it to do YYYYMMDD
    # or YYYY_MM_DD. it's unclear why.
    file_friendly_date = this_friday.replace("-", "")
    fn = os.path.join(OVERVIEWS_DIR, f"incident_overview_{file_friendly_date}.html")
    with open(fn, "w") as fp:
        fp.write(fixed_html)

    click.echo(f"Report written to: {fn}")
