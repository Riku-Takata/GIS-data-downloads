from datetime import date, datetime, timezone
from ftplib import error_perm
import json

import pytest

from app.services.gsmap_ftp_service import (
    GsmapRemoteFile,
    append_manifest,
    build_local_path,
    build_remote_directory,
    download_remote_file,
    is_matching_hourly_file,
    list_remote_files,
    normalize_product_path,
    parse_date_argument,
)


class FakeFtp:
    def __init__(self, payloads=None, *, mlsd_entries=None):
        self.payloads = payloads or {}
        self.mlsd_entries = mlsd_entries or []
        self.commands = []

    def mlsd(self, path, facts):
        self.commands.append(("MLSD", path, tuple(facts)))
        return iter(self.mlsd_entries)

    def retrbinary(self, command, callback, blocksize=8192, rest=None):
        self.commands.append(("RETR", command, rest))
        remote_path = command.removeprefix("RETR ")
        payload = self.payloads[remote_path]
        offset = rest or 0
        for index in range(offset, len(payload), blocksize):
            callback(payload[index : index + blocksize])


class NlstOnlyFakeFtp:
    def __init__(self, remote_path, size, modified):
        self.remote_path = remote_path
        self.remote_size = size
        self.modified = modified
        self.commands = []

    def mlsd(self, path, facts):
        self.commands.append(("MLSD", path))
        raise error_perm("502 MLSD not implemented")

    def nlst(self, path):
        self.commands.append(("NLST", path))
        return [self.remote_path]

    def size(self, path):
        self.commands.append(("SIZE", path))
        return self.remote_size

    def sendcmd(self, command):
        self.commands.append(("MDTM", command))
        return f"213 {self.modified}"


def test_product_and_date_validation():
    assert normalize_product_path("/standard/v8/") == "standard/v8"
    assert parse_date_argument("2014-01-02") == date(2014, 1, 2)
    assert parse_date_argument("today", today=date(2026, 8, 28)) == date(2026, 8, 28)

    with pytest.raises(ValueError):
        normalize_product_path("../standard/v8")
    with pytest.raises(ValueError):
        parse_date_argument("2014")


def test_hourly_directory_and_filename_matching():
    target_date = date(2014, 1, 2)
    assert (
        build_remote_directory("standard/v8", "hourly", target_date)
        == "/standard/v8/hourly/2014/01/02"
    )
    assert is_matching_hourly_file(
        "gsmap_mvk.20140102.2300.v8.0000.0.dat.gz",
        "hourly",
        target_date,
    )
    assert not is_matching_hourly_file(
        "gsmap_mvk.20140102.2300.v8.0000.0.sateinfo.dat.gz",
        "hourly",
        target_date,
    )
    assert not is_matching_hourly_file(
        "gsmap_mvk.20140103.0000.v8.0000.0.dat.gz",
        "hourly",
        target_date,
    )


def test_list_remote_files_uses_read_only_mlsd():
    ftp = FakeFtp(
        mlsd_entries=[
            (
                "gsmap_mvk.20140102.0000.v8.0000.0.dat.gz",
                {"type": "file", "size": "123", "modify": "20140105010203"},
            ),
            (
                "gsmap_mvk.20140102.0000.v8.0000.0.sateinfo.dat.gz",
                {"type": "file", "size": "456", "modify": "20140105010203"},
            ),
        ]
    )

    files = list_remote_files(
        ftp,
        product="standard/v8",
        dataset="hourly",
        target_date=date(2014, 1, 2),
    )

    assert len(files) == 1
    assert files[0].size == 123
    assert files[0].modified_at == datetime(2014, 1, 5, 1, 2, 3, tzinfo=timezone.utc)
    assert [command[0] for command in ftp.commands] == ["MLSD"]


def test_list_remote_files_falls_back_to_read_only_nlst():
    remote_path = "/standard/v8/hourly/2014/01/02/gsmap_mvk.20140102.0000.v8.0000.0.dat.gz"
    ftp = NlstOnlyFakeFtp(remote_path, 123, "20140105010203")

    files = list_remote_files(
        ftp,
        product="standard/v8",
        dataset="hourly",
        target_date=date(2014, 1, 2),
    )

    assert len(files) == 1
    assert files[0].remote_path == remote_path
    assert [command[0] for command in ftp.commands] == [
        "MLSD",
        "NLST",
        "SIZE",
        "MDTM",
    ]


def test_download_is_local_atomic_and_idempotent(tmp_path):
    payload = b"\x1f\x8b" + b"sample-gzip-payload"
    remote_path = "/standard/v8/hourly/2014/01/02/example.dat.gz"
    remote_file = GsmapRemoteFile(
        remote_path=remote_path,
        file_name="example.dat.gz",
        observation_date=date(2014, 1, 2),
        size=len(payload),
        modified_at=datetime(2014, 1, 5, tzinfo=timezone.utc),
    )
    ftp = FakeFtp({remote_path: payload})
    destination = build_local_path(
        tmp_path,
        "standard/v8",
        "hourly",
        remote_file,
    )

    result = download_remote_file(
        ftp,
        remote_file=remote_file,
        destination=destination,
    )

    assert result.status == "downloaded"
    assert destination.read_bytes() == payload
    assert not destination.with_name(destination.name + ".part").exists()
    assert result.sha256 is not None
    assert [command[0] for command in ftp.commands] == ["RETR"]

    skipped = download_remote_file(
        ftp,
        remote_file=remote_file,
        destination=destination,
    )
    assert skipped.status == "skipped"
    assert [command[0] for command in ftp.commands] == ["RETR"]


def test_manifest_is_json_lines(tmp_path):
    result = download_remote_file(
        FakeFtp({"/example": b"abc"}),
        remote_file=GsmapRemoteFile(
            remote_path="/example",
            file_name="example.dat.gz",
            observation_date=date(2014, 1, 2),
            size=3,
        ),
        destination=tmp_path / "example.dat.gz",
    )
    manifest = tmp_path / "manifest.jsonl"
    append_manifest(manifest, result)

    record = json.loads(manifest.read_text(encoding="utf-8"))
    assert record["status"] == "downloaded"
    assert record["remote_path"] == "/example"
    assert record["sha256"] == result.sha256
