# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from iim.iim_incident_data import iim_incident_data
from iim.libreport import IncidentReport


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def env_vars():
    return {
        "JIRA_URL": "https://jira.example.net",
        "JIRA_USERNAME": "user",
        "JIRA_TOKEN": "token",
    }


def make_report(**overrides):
    defaults = dict(
        key="IIM-42",
        jira_url="https://jira.example.net/browse/IIM-42",
        report_url="https://docs.google.com/document/d/ABC123/edit",
        report_modified="2026-03-01 12:00",
        summary="Test incident",
        description=None,
        severity="s2",
        status="Mitigated",
        entities="testservice",
        detection_method="alert",
        declare_date="2026-03-01",
        impact_start="2026-03-01T10:00:00.000-0000",
        declared="2026-03-01T10:05:00.000-0000",
        detected=None,
        alerted="2026-03-01T10:01:00.000-0000",
        acknowledged="2026-03-01T10:02:00.000-0000",
        responded="2026-03-01T10:03:00.000-0000",
        mitigated="2026-03-01T11:00:00.000-0000",
        resolved="2026-03-01T12:00:00.000-0000",
        action_items=[],
        labels=["completed"],
    )
    defaults.update(overrides)
    return IncidentReport(**defaults)


def invoke(runner, args, env_vars, client_secret_file, report):
    mock_jira = MagicMock()
    mock_jira.get_issue_report.return_value = report
    mock_service = MagicMock()

    with (
        patch.dict("os.environ", env_vars),
        patch("iim.iim_incident_data.JiraAPI", return_value=mock_jira),
        patch("iim.iim_incident_data.build_service", return_value=mock_service),
        patch("iim.iim_incident_data.update_report", side_effect=lambda svc, r: r),
    ):
        result = runner.invoke(
            iim_incident_data,
            ["--client-secret-file", client_secret_file] + list(args),
        )

    return result, mock_jira


def test_outputs_valid_json(runner, env_vars, client_secret_file):
    report = make_report()
    result, _ = invoke(runner, ["IIM-42"], env_vars, client_secret_file, report)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["key"] == "IIM-42"


def test_includes_dataclass_fields(runner, env_vars, client_secret_file):
    report = make_report()
    result, _ = invoke(runner, ["IIM-42"], env_vars, client_secret_file, report)
    data = json.loads(result.output)
    assert data["summary"] == "Test incident"
    assert data["severity"] == "s2"
    assert data["status"] == "Mitigated"
    assert data["entities"] == "testservice"
    assert data["declare_date"] == "2026-03-01"
    assert data["report_url"] == "https://docs.google.com/document/d/ABC123/edit"


def test_includes_computed_properties(runner, env_vars, client_secret_file):
    report = make_report()
    result, _ = invoke(runner, ["IIM-42"], env_vars, client_secret_file, report)
    data = json.loads(result.output)
    assert data["entity_bucket"] == "service"
    assert data["is_completed"] is True
    assert data["age"] is not None
    assert data["tt_declared"] is not None
    assert data["tt_alerted"] is not None
    assert data["tt_responded"] is not None
    assert data["tt_mitigated"] is not None
    assert data["tt_resolved"] is not None


def test_computed_properties_none_when_missing(runner, env_vars, client_secret_file):
    report = make_report(
        impact_start=None,
        declared=None,
        alerted=None,
        responded=None,
        mitigated=None,
        resolved=None,
        labels=[],
    )
    result, _ = invoke(runner, ["IIM-42"], env_vars, client_secret_file, report)
    data = json.loads(result.output)
    assert data["is_completed"] is False
    assert data["age"] is None
    assert data["tt_declared"] is None
    assert data["tt_alerted"] is None
    assert data["tt_responded"] is None
    assert data["tt_mitigated"] is None
    assert data["tt_resolved"] is None


def test_passes_issue_key_to_jira(runner, env_vars, client_secret_file):
    report = make_report()
    _, mock_jira = invoke(runner, ["IIM-99"], env_vars, client_secret_file, report)
    mock_jira.get_issue_report.assert_called_once_with("IIM-99")


def test_jira_client_uses_env_vars(runner, env_vars, client_secret_file):
    report = make_report()

    mock_jira_cls = MagicMock()
    mock_jira_cls.return_value.get_issue_report.return_value = report
    mock_service = MagicMock()

    with (
        patch.dict("os.environ", env_vars),
        patch("iim.iim_incident_data.JiraAPI", mock_jira_cls),
        patch("iim.iim_incident_data.build_service", return_value=mock_service),
        patch("iim.iim_incident_data.update_report", side_effect=lambda svc, r: r),
    ):
        runner.invoke(
            iim_incident_data,
            ["--client-secret-file", client_secret_file, "IIM-42"],
        )

    mock_jira_cls.assert_called_once_with(
        base_url="https://jira.example.net",
        username="user",
        password="token",
    )


def test_missing_issue_key_arg(runner, env_vars, client_secret_file):
    report = make_report()
    result, _ = invoke(runner, [], env_vars, client_secret_file, report)
    assert result.exit_code != 0
    assert "Missing argument" in result.output
