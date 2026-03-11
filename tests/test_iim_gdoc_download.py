# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from googleapiclient.errors import HttpError

from iim.iim_gdoc_download import (
    extract_doc_id,
    iim_gdoc_download,
    title_to_filename,
)


# ---------------------------------------------------------------------------
# title_to_filename
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "title, expected",
    [
        ("My Document", "my_document.md"),
        ("Incident Report: Q1 2026!", "incident_report_q1_2026.md"),
        ("  leading and trailing  ", "leading_and_trailing.md"),
        ("multiple   spaces", "multiple_spaces.md"),
        ("hyphen-separated", "hyphen-separated.md"),
        ("already_underscored", "already_underscored.md"),
        ("special!@#$%^&*()chars", "specialchars.md"),
        ("UPPERCASE TITLE", "uppercase_title.md"),
    ],
)
def test_title_to_filename(title, expected):
    assert title_to_filename(title) == expected


# ---------------------------------------------------------------------------
# extract_doc_id
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url, expected_id",
    [
        (
            "https://docs.google.com/document/d/1O0KXJlklGcQzr2CYb3MTGyS_ZO2B3R0x532bPaxXyL4/edit",
            "1O0KXJlklGcQzr2CYb3MTGyS_ZO2B3R0x532bPaxXyL4",
        ),
        (
            "https://docs.google.com/document/d/ABC123/edit?usp=sharing",
            "ABC123",
        ),
        (
            "https://docs.google.com/document/d/ABC-123_xyz/view",
            "ABC-123_xyz",
        ),
    ],
)
def test_extract_doc_id_valid(url, expected_id):
    assert extract_doc_id(url) == expected_id


def test_extract_doc_id_invalid():
    with pytest.raises(ValueError, match="Could not extract document ID"):
        extract_doc_id("https://google.com/not-a-doc")


# ---------------------------------------------------------------------------
# iim_gdoc_download CLI
# ---------------------------------------------------------------------------


DOC_ID = "DOC123"
DOC_URL = f"https://docs.google.com/document/d/{DOC_ID}/edit"
DOC_NAME = "My Document"
DOC_CONTENT = b"# My Document\n\nHello world.\n"


def make_fake_downloader(content):
    """Return a MediaIoBaseDownload replacement that writes content to the buffer."""

    class FakeDownloader:
        def __init__(self, buffer, request):
            self._buffer = buffer
            self._done = False

        def next_chunk(self):
            if not self._done:
                self._buffer.write(content)
                self._done = True
            return (None, True)

    return FakeDownloader


def make_mock_service(doc_name=DOC_NAME):
    mock_service = MagicMock()
    mock_service.files.return_value.get.return_value.execute.return_value = {
        "name": doc_name
    }
    return mock_service


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def client_secret_file(tmp_path):
    """A minimal client secret JSON file that satisfies click.Path(exists=True)."""
    path = tmp_path / "client_secret.json"
    path.write_text(json.dumps({"installed": {"client_id": "test"}}))
    return str(path)


def invoke(
    runner,
    args,
    input=None,
    client_secret_file=None,
    output_dir=None,
    mock_service=None,
    content=DOC_CONTENT,
):
    mock_service = mock_service or make_mock_service()
    cli_args = []
    if client_secret_file:
        cli_args += ["--client-secret-file", client_secret_file]
    if output_dir:
        cli_args += ["--output-dir", str(output_dir)]
    cli_args += list(args)

    with (
        patch("iim.iim_gdoc_download.get_credentials", return_value=MagicMock()),
        patch("iim.iim_gdoc_download.build", return_value=mock_service),
        patch(
            "iim.iim_gdoc_download.MediaIoBaseDownload", make_fake_downloader(content)
        ),
    ):
        return runner.invoke(iim_gdoc_download, cli_args, input=input)


# --- single URL as argument ---


def test_cli_single_url(runner, client_secret_file, tmp_path):
    result = invoke(
        runner,
        args=[DOC_URL],
        client_secret_file=client_secret_file,
        output_dir=tmp_path,
    )
    assert result.exit_code == 0
    output_file = tmp_path / "my_document.md"
    assert output_file.exists()
    assert output_file.read_bytes() == DOC_CONTENT


def test_cli_single_url_output_message(runner, client_secret_file, tmp_path):
    result = invoke(
        runner,
        args=[DOC_URL],
        client_secret_file=client_secret_file,
        output_dir=tmp_path,
    )
    assert "Saved to" in result.output
    assert "my_document.md" in result.output


# --- multiple URLs as arguments ---


def test_cli_multiple_urls(runner, client_secret_file, tmp_path):
    doc2_id = "DOC456"
    doc2_url = f"https://docs.google.com/document/d/{doc2_id}/edit"
    doc2_name = "Second Document"
    # doc2_content = b"# Second Document\n\nContent.\n"

    mock_service = MagicMock()
    mock_service.files.return_value.get.return_value.execute.side_effect = [
        {"name": DOC_NAME},
        {"name": doc2_name},
    ]

    with (
        patch("iim.iim_gdoc_download.get_credentials", return_value=MagicMock()),
        patch("iim.iim_gdoc_download.build", return_value=mock_service),
        patch(
            "iim.iim_gdoc_download.MediaIoBaseDownload",
            make_fake_downloader(DOC_CONTENT),
        ),
    ):
        result = runner.invoke(
            iim_gdoc_download,
            [
                "--client-secret-file",
                client_secret_file,
                "--output-dir",
                str(tmp_path),
                DOC_URL,
                doc2_url,
            ],
        )

    assert result.exit_code == 0
    assert (tmp_path / "my_document.md").exists()
    assert (tmp_path / "second_document.md").exists()


# --- URLs from stdin ---


def test_cli_stdin(runner, client_secret_file, tmp_path):
    result = invoke(
        runner,
        args=[],
        input=DOC_URL + "\n",
        client_secret_file=client_secret_file,
        output_dir=tmp_path,
    )
    assert result.exit_code == 0
    assert (tmp_path / "my_document.md").exists()


def test_cli_stdin_multiple_urls(runner, client_secret_file, tmp_path):
    doc2_url = "https://docs.google.com/document/d/DOC456/edit"

    mock_service = MagicMock()
    mock_service.files.return_value.get.return_value.execute.side_effect = [
        {"name": DOC_NAME},
        {"name": "Second Document"},
    ]

    with (
        patch("iim.iim_gdoc_download.get_credentials", return_value=MagicMock()),
        patch("iim.iim_gdoc_download.build", return_value=mock_service),
        patch(
            "iim.iim_gdoc_download.MediaIoBaseDownload",
            make_fake_downloader(DOC_CONTENT),
        ),
    ):
        result = runner.invoke(
            iim_gdoc_download,
            ["--client-secret-file", client_secret_file, "--output-dir", str(tmp_path)],
            input=f"{DOC_URL}\n{doc2_url}\n",
        )

    assert result.exit_code == 0
    assert (tmp_path / "my_document.md").exists()
    assert (tmp_path / "second_document.md").exists()


def test_cli_stdin_ignores_blank_lines(runner, client_secret_file, tmp_path):
    result = invoke(
        runner,
        args=[],
        input=f"\n{DOC_URL}\n\n",
        client_secret_file=client_secret_file,
        output_dir=tmp_path,
    )
    assert result.exit_code == 0
    assert (tmp_path / "my_document.md").exists()


# --- error cases ---


def test_cli_no_urls_no_stdin(runner, client_secret_file, tmp_path):
    # Simulate a tty by not providing input — CliRunner stdin is not a tty,
    # so we verify the fallback stdin path handles an empty stream gracefully.
    output_dir = tmp_path / "reports"
    output_dir.mkdir()
    result = invoke(
        runner,
        args=[],
        input="",
        client_secret_file=client_secret_file,
        output_dir=output_dir,
    )
    assert result.exit_code == 0
    # No files written for empty stdin
    assert list(output_dir.iterdir()) == []


def test_cli_invalid_url(runner, client_secret_file, tmp_path):
    result = invoke(
        runner,
        args=["https://google.com/not-a-doc"],
        client_secret_file=client_secret_file,
        output_dir=tmp_path,
    )
    assert result.exit_code != 0


def test_cli_api_404(runner, client_secret_file, tmp_path):
    mock_service = MagicMock()
    resp = MagicMock()
    resp.status = 404
    mock_service.files.return_value.get.return_value.execute.side_effect = HttpError(
        resp=resp, content=b"File not found"
    )

    with (
        patch("iim.iim_gdoc_download.get_credentials", return_value=MagicMock()),
        patch("iim.iim_gdoc_download.build", return_value=mock_service),
        patch(
            "iim.iim_gdoc_download.MediaIoBaseDownload",
            make_fake_downloader(DOC_CONTENT),
        ),
    ):
        result = runner.invoke(
            iim_gdoc_download,
            [
                "--client-secret-file",
                client_secret_file,
                "--output-dir",
                str(tmp_path),
                DOC_URL,
            ],
        )

    assert result.exit_code != 0


# --- output directory ---


def test_cli_creates_output_dir(runner, client_secret_file, tmp_path):
    output_dir = tmp_path / "nested" / "reports"
    result = invoke(
        runner,
        args=[DOC_URL],
        client_secret_file=client_secret_file,
        output_dir=output_dir,
    )
    assert result.exit_code == 0
    assert (output_dir / "my_document.md").exists()
