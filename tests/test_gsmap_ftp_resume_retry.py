from datetime import date
from unittest.mock import MagicMock

from app.services.gsmap_ftp_retry_service import run_ftp_operation_with_retry
from app.services.gsmap_ftp_service import (
    GsmapFtpConfig,
    GsmapRemoteFile,
    download_remote_file,
)


def test_mid_transfer_disconnect_resumes_part_file_after_reconnect(tmp_path):
    payload = b"0123456789abcdef"
    remote = GsmapRemoteFile(
        remote_path="/standard/v8/hourly/2023/06/29/example.dat.gz",
        file_name="example.dat.gz",
        observation_date=date(2023, 6, 29),
        size=len(payload),
    )
    destination = tmp_path / remote.file_name

    first = MagicMock()

    def interrupted(command, callback, blocksize, rest):
        assert rest is None
        callback(payload[:6])
        raise ConnectionResetError("connection reset during transfer")

    first.retrbinary.side_effect = interrupted
    second = MagicMock()

    def resumed(command, callback, blocksize, rest):
        assert rest == 6
        callback(payload[rest:])

    second.retrbinary.side_effect = resumed
    connect = MagicMock(side_effect=[first, second])
    config = GsmapFtpConfig("ftp.example.test", 21, "user", "password")

    result, active = run_ftp_operation_with_retry(
        None,
        config,
        lambda ftp: download_remote_file(
            ftp,
            remote_file=remote,
            destination=destination,
            resume=True,
        ),
        retries=1,
        base_delay_seconds=0,
        sleep=MagicMock(),
        connect=connect,
    )

    assert result.status == "downloaded"
    assert active is second
    assert destination.read_bytes() == payload
    assert not destination.with_name(destination.name + ".part").exists()
