#!/usr/bin/env python
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "arrow",
#     "click",
#     "css_inline",
#     "glom",
#     "jinja2",
#     "python-dotenv",
#     "requests",
#     "rich",
# ]
# ///

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Computes a weekly report for incidents.
"""

import os
from datetime import timedelta

import arrow
import click
import css_inline
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, select_autoescape

from libjira import (
    fix_incident_data,
    generate_jira_link,
    get_all_issues_for_project,
)


OVERVIEWS_DIR = "incident_overviews"


load_dotenv()


def humanize_timedelta(td: timedelta) -> str:
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


@click.command()
@click.pass_context
def iim_weekly_report(ctx):
    """
    Computes a weekly report based on Jira data. Make sure to update the data
    in Jira and then run `iim_data.py` before running the report.

    Create an API token in Jira and set these in the `.env` file:

    \b
    * JIRA_USERNAME
    * JIRA_PASSWORD
    * JIRA_URL
    """
    username = os.environ["JIRA_USERNAME"].strip()
    password = os.environ["JIRA_PASSWORD"].strip()
    url = os.environ["JIRA_URL"].strip().rstrip("/")

    if not os.path.exists(OVERVIEWS_DIR):
        os.mkdir(OVERVIEWS_DIR)

    issue_data = get_all_issues_for_project(
        jira_base_url=url,
        project_key="IIM",
        username=username,
        password=password,
    )

    incidents = [fix_incident_data(jira_url=url, incident=incident) for incident in issue_data]

    # Calculate incident outage time
    now = arrow.now()
    for incident in incidents:
        timings = {
            "ttd": "?",
            "ttm": "?",
        }
        start_ts = incident["impact start"] or incident["detected"]
        if not start_ts:
            incident.update(timings)
            continue

        if incident["detected"]:
            end_ts = arrow.get(incident["detected"])
            timings["ttd"] = humanize_timedelta(end_ts - arrow.get(start_ts))

        if incident["mitigated"]:
            end_ts = arrow.get(incident["mitigated"])
            timings["ttm"] = humanize_timedelta(end_ts - arrow.get(start_ts))
        else:
            timings["ttm"] = humanize_timedelta(now - arrow.get(start_ts)) + " (ongoing)"

        incident.update(timings)

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
            incident["declare date"][0:11] >= last_friday
            and incident["declare date"][0:11] <= this_friday
        )
    ]

    severity_breakdown = {}
    for item in new_incidents:
        severity_breakdown[item["severity"]] = (
            severity_breakdown.get(item["severity"], 0) + 1
        )

    active_incidents = [
        incident for incident in incidents if incident["status"] != "Resolved"
    ]

    env = Environment(
        loader=FileSystemLoader("templates"), autoescape=select_autoescape()
    )

    template = env.get_template("incident_overview.html")
    html = template.render(
        title=f"Weekly Incident Overview: {this_friday}",
        this_friday=this_friday,
        last_friday=last_friday,
        num_incidents=len(new_incidents),
        num_s1_incidents=severity_breakdown.get("S1", 0),
        num_s2_incidents=severity_breakdown.get("S2", 0),
        num_s3_incidents=severity_breakdown.get("S3", 0),
        num_s4_incidents=severity_breakdown.get("S4", 0),
        new_incidents=new_incidents,
        new_incidents_link=generate_jira_link(
            jira_url=url,
            incident_keys=[item["key"] for item in new_incidents],
        ),
        active_incidents=active_incidents,
        active_incidents_link=generate_jira_link(
            jira_url=url,
            incident_keys=[item["key"] for item in active_incidents],
        ),
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


if __name__ == "__main__":
    iim_weekly_report()
