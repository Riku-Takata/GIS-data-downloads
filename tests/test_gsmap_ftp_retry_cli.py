import json
from unittest.mock import MagicMock, patch

from scripts.download_gsmap import main as download_gsmap_main


def test_cli_reconnects_after_passive_data_connection_refusal(
    monkeypatch, capsys, tmp_path
):
    monkeypatch.setenv("GSMAP_FTP_HOST", "ftp.example.test")
    monkeypatch.setenv("GSMAP_FTP_USER", "example-user")
    monkeypatch.setenv("GSMAP_FTP_PASSWORD", "example-password")
    payload = b"complete-after-reconnect"

    first = MagicMock()
    first.mlsd.return_value = iter(
        [
            (
                "gsmap_mvk.20230629.0800.v8.0000.0.dat.gz",
                {"type": "file", "size": str(len(payload))},
            )
        ]
    )
    first.retrbinary.side_effect = ConnectionRefusedError(
        10061, "passive data connection refused"
    )

    second = MagicMock()

    def retrieve(command, callback, blocksize, rest):
        assert rest is None
        callback(payload)

    second.retrbinary.side_effect = retrieve

    with patch("scripts.download_gsmap.open_ftp", side_effect=[first, second]):
        exit_code = download_gsmap_main(
            [
                "standard/v8",
                "--start",
                "2023-06-29",
                "--end",
                "2023-06-29",
                "--output-dir",
                str(tmp_path),
                "--ftp-retries",
                "2",
                "--retry-delay",
                "0",
                "--retry-max-delay",
                "0",
                "--quiet",
            ]
        )

    assert exit_code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["downloaded"] == 1
    assert summary["ftp_retries"] == 1
    destination = (
        tmp_path
        / "standard"
        / "v8"
        / "hourly"
        / "2023"
        / "06"
        / "29"
        / "gsmap_mvk.20230629.0800.v8.0000.0.dat.gz"
    )
    assert destination.read_bytes() == payload
    first.quit.assert_called_once()
    second.quit.assert_called_once()
