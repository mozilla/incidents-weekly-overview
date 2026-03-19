# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import pytest

from iim.libjira import JiraAPI


@pytest.fixture
def jira_client():
    return JiraAPI(
        base_url="https://jira.example.com", username="user", password="pass"
    )
