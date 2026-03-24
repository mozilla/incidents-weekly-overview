# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import json

import pytest

from iim.libjira import JiraAPI


@pytest.fixture
def jira_client():
    return JiraAPI(
        base_url="https://jira.example.com", username="user", password="pass"
    )


@pytest.fixture
def client_secret_file(tmp_path):
    """A minimal client secret JSON file that satisfies click.Path(exists=True)."""
    path = tmp_path / "client_secret.json"
    path.write_text(json.dumps({"installed": {"client_id": "test"}}))
    return str(path)
