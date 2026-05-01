# incidents-weekly-overview

Tooling for Mozilla's incident management process: weekly overview emails, QBR
stats, syncing incident report data to Jira, and more.

# Setup

## Environment

All scripts require environment variables to be set.

Copy `env.tmpl` to `.env`. You'll fill in values using instructions below.

## Jira API token

All scripts that query Jira need `JIRA_USERNAME`, `JIRA_TOKEN`, and `JIRA_URL`
set in `.env`.

To generate an API token:

1. Log in to your Atlassian account and go to
   *Account Settings → Security → API tokens*.
2. Click **Create API token**, give it a label, and copy the token value.
3. Set `JIRA_USERNAME` in `.env` to your Atlassian account email address.
4. Set `JIRA_TOKEN` in `.env` to the token you just copied.
5. Set `JIRA_URL` in `.env` to the base URL of your Jira instance

## Google Drive API credentials

The `iim-data`, `iim-gdoc-download`, `iim-incident-data`, `iim-sync`, and
`iim-lint` commands require Google Drive API credentials. One-time setup:

1. Go to the [Google Cloud Console](https://console.cloud.google.com/) and
   create a project (or select an existing one).
2. Enable the **Google Drive API** for the project under *APIs & Services →
   Enabled APIs*.
3. Go to *APIs & Services → Credentials*, click **Create Credentials →
   OAuth client ID**, and choose **Desktop app** as the application type.
4. Download the resulting JSON file and save it as `client_secret.json` in the
   repository root (this path is the default; you can pass a different path
   with `--client-secret-file`).
5. On first run, a browser window will open asking you to authorise access.
   After you approve, the token is cached in `.gdrive/oauth_token.json` and
   subsequent runs will not prompt again (it refreshes automatically).

## Python

Run `uv sync` from the repository root to install the package and its
dependencies.


# Usage

`uv run iim-data [--show ...] [--period ...] [--output all|FIELDS]`

Lists all incidents from Jira. Use `--show` to filter to a view
(`working`, `resolved`, `active`, `dormant`) and `--period` to set the
time window. Use `--output` to control the output format: `all` (the
default) prints full human-readable details, or pass a comma-separated
list of `IncidentReport` fields (e.g.
`--output key,jira_url,report_url`) to print one CSV row per incident
with a header row.

`uv run iim-incident-data ISSUE_KEY`

Downloads Jira data for a single incident (e.g. `IIM-141`) and outputs it as
JSON. Useful for debugging.

`uv run iim-gdoc-download [SOURCE...]`

Downloads one or more Google Docs as Markdown files into the `reports/`
directory. Sources can be Google Doc URLs, Jira issue keys (e.g. `IIM-123`),
or Jira browse URLs. If no arguments are given, reads one source per line from
stdin.

`uv run iim-gdocs-to-jira [--dry-run] FILE [FILE...]`

Parses incident report Markdown files (exported from Google Docs via
*File → Download → Markdown*) and syncs their metadata back to Jira.
Pushes changes by default; pass `--dry-run` to preview the diff without
committing anything.

`uv run iim-sync [--dry-run] [URL_OR_KEY...]`

Downloads the Google Doc for each incident, shows a diff against the current
Jira data, and interactively lets you apply, skip, or retry each change. Pass
`--dry-run` to show the diff without pushing changes to Jira. Accepts full
Jira browse URLs or bare issue keys (e.g. `IIM-131`); reads from stdin if no
arguments are given.

`uv run iim-lint [ARGS...]`

Lints IIM incident issues for data quality problems. Arguments can be Jira
issue keys, Jira browse URLs, or Google Doc URLs. Use `--list-rules` to see
all available rules and `--errors-only` to suppress warnings.

`uv run iim-to-review`

Lists resolved incidents that have not yet been marked as completed.

`uv run iim-mpir-selection [--weeks N]`

Lists service incidents declared in the last N weeks (default: 5) as
candidates for the monthly post-incident review meeting.

`uv run iim-weekly-overview [--friday YYYY-MM-DD]`

Queries Jira and generates a weekly overview as HTML in the
`incident_overviews/` directory. Defaults to the current week's Friday; pass
`--friday` to generate for a specific date.

You can then open the output file in Firefox and copy-and-paste it into an
email to send to the incidents-overview mailing list.

`uv run iim-qbr PERIOD`

Queries Jira and computes QBR statistics for the specified period.

PERIOD can be one of:

* `all` — all data
* `YYYY` — all data for a specific year
* `YYYYqN` — all data for a specific quarter (e.g. `2025q4`)

Outputs a summary table to the terminal and writes a CSV of incident data to
`qbr_stats_PERIOD.csv`.

`uv run convert-timezone`

Converts timestamps from local timezone to UTC, handling DST correctly.


# Dev things

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
