# incidents-weekly-overview

Code for Weekly Incidents Overview email, tooling, etc

# Setup

Copy `env.tmpl` to `.env` and then fill in the three values per the
instructions in the file.

Scripts are run directly from a repository checkout.

# usage

`uv run scripts/iim_active.py`

Queries Jira and outputs a list of active incidents.

`uv run scripts/iim_gdocs_to_jira.py [FILE...]`

Given a set of Markdown files generated from doing "File -> Download ->
Markdown" in Google Docs for each incident report, this queries Jira,
determines what needs to be updated, and updates it.

By default, this makes no changes. You must pass the `--commit` flag to have it
push changes to Jira.

**Note: Make sure your Markdown files aren't stale.**

`uv run scripts/iim_weekly_overview.py`

Queries Jira and generates a weekly overview as HTML in the
`incident_overviews` directory.

You can then open this in Firefox and copy-and-paste it into an email to send
to the incidents-overview mailing list.

# dev things

Uses [just](https://just.systems/`) for project commands.

```
just lint
just format
```

TBD: tests

# License

Released under the MPLv2. See
[LICENSE](https://github.com/mozilla/incidents-weekly-overview/blob/main/LICENSE).
