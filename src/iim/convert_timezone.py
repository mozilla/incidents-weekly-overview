#!/usr/bin/env python
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "arrow",
#     "click",
#     "tzlocal",
# ]
# ///

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import arrow
import click
import tzlocal


def convert_timestamp(tzinfo, ts_str):
    return arrow.get(ts_str).replace(tzinfo=tzinfo).to("UTC").format("YYYY-MM-DD HH:mm")


@click.command()
@click.pass_context
def convert_timezone(ctx):
    """Converts timestamps from local timezone (e.g. "America/New_York) to UTC

    Handles daylight savings time correctly.

    \b
    $ uv run convert-timezone
    Convert timestamps in YYYY-MM-DD hh:mm format. Example: 2026-01-01 04:44
    Timezone: America/New_York
    Timestamp? (CTRL-C to exit) : 2026-03-11 08:00
    2026-03-11 12:00
    Timestamp? (CTRL-C to exit) : 2026-03-01 08:00
    2026-03-01 13:00

    """
    tz_name = tzlocal.get_localzone_name()

    click.echo(
        "Convert timestamps in YYYY-MM-DD hh:mm format. Example: 2026-01-01 04:44"
    )
    click.echo(f"Timezone: {tz_name}")
    while True:
        timestamp = click.prompt("Timestamp? (CTRL-C to exit) ")
        try:
            click.echo(convert_timestamp(tzinfo=tz_name, ts_str=timestamp))
        except Exception as exc:
            click.echo(exc)


if __name__ == "__main__":
    convert_timezone()
