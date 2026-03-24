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

The `iim-data` and `iim-gdoc-download` commands require Google Drive API
credentials. One-time setup:

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
