from ftplib import error_perm
from unittest.mock import MagicMock

import pytest

from app.services.gsmap_ftp_retry_service import (
    is_retryable_ftp_error,
    run_ftp_operation_with_retry,
)
from app.services.gsmap_ftp_service import GsmapFtpConfig


def _config():
    return GsmapFtpConfig(
        host="ftp.example.test",
        port=21,
        username="user",
        password="password",
    )


def test_connection_refused_reconnects_and_retries():
    first = MagicMock()
    second = MagicMock()
    connect = MagicMock(side_effect=[first, second])
    sleeps = []
    retries = []

    def operation(ftp):
        if ftp is first:
            raise ConnectionRefusedError(10061, "passive data connection refused")
        return "completed"

    result, active = run_ftp_operation_with_retry(
        None,
        _config(),
        operation,
        retries=3,
        base_delay_seconds=2,
        max_delay_seconds=30,
        on_retry=lambda attempt, total, delay, exc: retries.append(
            (attempt, total, delay, type(exc))
        ),
        sleep=sleeps.append,
        connect=connect,
    )

    assert result == "completed"
    assert active is second
    assert connect.call_count == 2
    first.quit.assert_called_once()
    assert sleeps == [2]
    assert retries == [(1, 3, 2, ConnectionRefusedError)]


def test_exponential_delay_is_capped_and_last_error_is_raised():
    connections = [MagicMock() for _ in range(4)]
    sleeps = []

    with pytest.raises(ConnectionResetError):
        run_ftp_operation_with_retry(
            None,
            _config(),
            lambda ftp: (_ for _ in ()).throw(ConnectionResetError("reset")),
            retries=3,
            base_delay_seconds=10,
            max_delay_seconds=15,
            sleep=sleeps.append,
            connect=MagicMock(side_effect=connections),
        )

    assert sleeps == [10, 15, 15]
    assert all(connection.quit.call_count == 1 for connection in connections)


def test_permanent_authentication_error_is_not_retried():
    ftp = MagicMock()
    connect = MagicMock(return_value=ftp)

    with pytest.raises(error_perm):
        run_ftp_operation_with_retry(
            None,
            _config(),
            lambda client: (_ for _ in ()).throw(error_perm("530 Login incorrect")),
            retries=8,
            sleep=MagicMock(),
            connect=connect,
        )

    assert connect.call_count == 1
    ftp.quit.assert_not_called()


@pytest.mark.parametrize(
    "exc",
    [ConnectionRefusedError(), ConnectionResetError(), TimeoutError(), EOFError()],
)
def test_retryable_network_errors(exc):
    assert is_retryable_ftp_error(exc)


def test_local_file_error_is_not_retryable():
    assert not is_retryable_ftp_error(FileNotFoundError("local file missing"))
