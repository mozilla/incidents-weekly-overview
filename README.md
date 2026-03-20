# incidents-weekly-overview

Tooling for Mozilla's incident management process: weekly overview emails, QBR
stats, syncing incident report data to Jira, and more.

# Setup

Copy `env.tmpl` to `.env` and then fill in the three values per the
instructions in the file.

Run `uv sync` from the repository root to install the package and its
dependencies.

# usage

`uv run iim-active`

Queries Jira and outputs a list of active incidents.

`uv run iim-gdocs-to-jira FILE [FILE...]`

Given a set of Markdown files generated from doing "File -> Download ->
Markdown" in Google Docs for each incident report, this queries Jira,
determines what needs to be updated, and updates it.

By default, this makes no changes. You must pass the `--commit` flag to have it
push changes to Jira.

**Note: Make sure your Markdown files aren't stale.**

`uv run iim-gdoc-download GDOC_URL [GDOC_URL...]`

Downloads one or more Google Docs as Markdown files into the `reports/`
directory. URLs can also be piped via stdin.

`uv run iim-weekly-overview`

Queries Jira and generates a weekly overview as HTML in the
`incident_overviews` directory.

You can then open this in Firefox and copy-and-paste it into an email to send
to the incidents-overview mailing list.

`uv run iim-qbr PERIOD`

Queries Jira and computes QBR statistics for the specified period. Uses
`monthly_review_data.json` (in the working directory) to determine which
incidents were reviewed and how many S1/S2 incidents were reviewed.

PERIOD can be one of:

* `all` — all data
* `YYYY` — all data for a specific year
* `YYYYqN` — all data for a specific quarter (e.g. `2025q4`)

Outputs a summary table to the terminal and writes a CSV of incident data to
`qbr_stats_PERIOD.csv`.

# dev things

Uses [just](https://just.systems/) for project commands.

```
just lint
just format
just test
just typecheck
```

# License

Released under the MPLv2. See
[LICENSE](https://github.com/mozilla/incidents-weekly-overview/blob/main/LICENSE).
