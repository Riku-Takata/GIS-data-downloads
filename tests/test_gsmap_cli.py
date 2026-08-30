import json
from unittest.mock import MagicMock, patch

import pytest

from scripts.download_gsmap import main as download_gsmap_main


def _configured_environment(monkeypatch):
    monkeypatch.setenv("GSMAP_FTP_HOST", "ftp.example.test")
    monkeypatch.setenv("GSMAP_FTP_USER", "example-user")
    monkeypatch.setenv("GSMAP_FTP_PASSWORD", "example-password")


def test_large_range_requires_explicit_yes(capsys):
    with pytest.raises(SystemExit) as exc_info:
        download_gsmap_main(
            [
                "standard/v8",
                "--start",
                "2014-01-01",
                "--end",
                "2014-02-02",
            ]
        )
    assert exc_info.value.code == 2
    assert "--yes" in capsys.readouterr().err


def test_dry_run_lists_without_retrieving(monkeypatch, capsys):
    _configured_environment(monkeypatch)
    ftp = MagicMock()
    ftp.mlsd.return_value = iter(
        [
            (
                "gsmap_mvk.20140102.0000.v8.0000.0.dat.gz",
                {"type": "file", "size": "123", "modify": "20140105010203"},
            )
        ]
    )

    with patch("scripts.download_gsmap.open_ftp", return_value=ftp):
        exit_code = download_gsmap_main(
            [
                "standard/v8",
                "--start",
                "2014-01-02",
                "--end",
                "2014-01-02",
                "--dry-run",
                "--quiet",
            ]
        )

    assert exit_code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "dry-run"
    assert summary["files_found"] == 1
    assert summary["remote_bytes_known"] == 123
    ftp.retrbinary.assert_not_called()
    ftp.quit.assert_called_once()


def test_cli_downloads_to_local_hierarchy(monkeypatch, capsys, tmp_path):
    _configured_environment(monkeypatch)
    payload = b"\x1f\x8bexample"
    ftp = MagicMock()
    ftp.mlsd.return_value = iter(
        [
            (
                "gsmap_mvk.20140102.0000.v8.0000.0.dat.gz",
                {
                    "type": "file",
                    "size": str(len(payload)),
                    "modify": "20140105010203",
                },
            )
        ]
    )

    def retrieve(command, callback, blocksize, rest):
        assert command.startswith("RETR /standard/v8/hourly/")
        assert rest is None
        callback(payload)

    ftp.retrbinary.side_effect = retrieve

    with patch("scripts.download_gsmap.open_ftp", return_value=ftp):
        exit_code = download_gsmap_main(
            [
                "standard/v8",
                "--start",
                "2014-01-02",
                "--end",
                "2014-01-02",
                "--output-dir",
                str(tmp_path),
                "--quiet",
            ]
        )

    assert exit_code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["downloaded"] == 1
    destination = (
        tmp_path
        / "standard"
        / "v8"
        / "hourly"
        / "2014"
        / "01"
        / "02"
        / "gsmap_mvk.20140102.0000.v8.0000.0.dat.gz"
    )
    assert destination.read_bytes() == payload
    records = [
        json.loads(line)
        for line in (tmp_path / "manifest.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert records[0]["status"] == "downloaded"
    assert records[0]["remote_path"].startswith("/standard/v8/hourly/")
