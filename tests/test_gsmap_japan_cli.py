from datetime import date
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.gsmap_japan_csv_service import GsmapCsvResult, GsmapGridCell
from scripts.download_gsmap import main as download_gsmap_main


def test_cli_runs_japan_csv_conversion_after_download(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("GSMAP_FTP_HOST", "ftp.example.test")
    monkeypatch.setenv("GSMAP_FTP_USER", "example-user")
    monkeypatch.setenv("GSMAP_FTP_PASSWORD", "example-password")
    payload = b"downloaded-binary"
    ftp = MagicMock()
    ftp.mlsd.return_value = iter(
        [
            (
                "gsmap_mvk.20140102.0000.v8.0000.0.dat.gz",
                {"type": "file", "size": str(len(payload))},
            )
        ]
    )

    def retrieve(command, callback, blocksize, rest):
        callback(payload)

    ftp.retrbinary.side_effect = retrieve

    def convert(source_paths, output_path, cells, **kwargs):
        assert len(source_paths) == 1
        assert source_paths[0].read_bytes() == payload
        assert cells == [GsmapGridCell(row=249, column=1390)]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("timestamp_utc,grid_id\n", encoding="utf-8")
        return GsmapCsvResult(
            status="converted",
            output_path=output_path,
            observation_date=date(2014, 1, 2),
            source_files=1,
            grid_cells=1,
            rows=1,
            size=output_path.stat().st_size,
        )

    binary_dir = tmp_path / "binary"
    csv_dir = tmp_path / "csv"
    with (
        patch("scripts.download_gsmap.open_ftp", return_value=ftp),
        patch(
            "scripts.download_gsmap.load_or_build_japan_grid_mask",
            return_value=[GsmapGridCell(row=249, column=1390)],
        ),
        patch("scripts.download_gsmap.convert_gsmap_day_to_csv", side_effect=convert),
    ):
        exit_code = download_gsmap_main(
            [
                "standard/v8",
                "--start",
                "2014-01-02",
                "--end",
                "2014-01-02",
                "--output-dir",
                str(binary_dir),
                "--japan-csv",
                "--japan-csv-dir",
                str(csv_dir),
                "--japan-boundary",
                str(tmp_path / "boundary.zip"),
                "--quiet",
            ]
        )

    assert exit_code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["japan_csv"]["enabled"] is True
    assert summary["japan_csv"]["grid_cells"] == 1
    assert summary["japan_csv"]["days_converted"] == 1
    assert summary["japan_csv"]["rows"] == 1
    assert (csv_dir / "standard/v8/hourly/2014/01/20140102.csv.gz").is_file()
