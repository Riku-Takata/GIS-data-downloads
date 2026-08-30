"""Retry and reconnect support for long-running GSMaP FTP operations."""

from __future__ import annotations

from collections.abc import Callable
import errno
from ftplib import FTP, error_proto, error_reply, error_temp
import time
from typing import TypeVar

from app.services.gsmap_ftp_service import GsmapFtpConfig, open_ftp


ResultT = TypeVar("ResultT")
RetryCallback = Callable[[int, int, float, BaseException], None]

_RETRYABLE_ERRNOS = {
    errno.ECONNABORTED,
    errno.ECONNREFUSED,
    errno.ECONNRESET,
    errno.EHOSTUNREACH,
    errno.ENETUNREACH,
    errno.EPIPE,
    errno.ETIMEDOUT,
}
_RETRYABLE_WINERRORS = {10051, 10053, 10054, 10060, 10061, 10064, 10065}


def is_retryable_ftp_error(exc: BaseException) -> bool:
    """Return whether reconnecting can reasonably recover from this failure."""
    if isinstance(
        exc,
        (ConnectionError, TimeoutError, EOFError, error_temp, error_reply, error_proto),
    ):
        return True
    if isinstance(exc, OSError):
        return (
            exc.errno in _RETRYABLE_ERRNOS
            or getattr(exc, "winerror", None) in _RETRYABLE_WINERRORS
        )
    return False


def close_ftp_quietly(ftp: FTP | None) -> None:
    if ftp is None:
        return
    try:
        ftp.quit()
    except Exception:
        try:
            ftp.close()
        except Exception:
            pass


def run_ftp_operation_with_retry(
    ftp: FTP | None,
    config: GsmapFtpConfig,
    operation: Callable[[FTP], ResultT],
    *,
    retries: int = 8,
    base_delay_seconds: float = 5.0,
    max_delay_seconds: float = 120.0,
    on_retry: RetryCallback | None = None,
    sleep: Callable[[float], None] = time.sleep,
    connect: Callable[[GsmapFtpConfig], FTP] = open_ftp,
) -> tuple[ResultT, FTP]:
    """Run an FTP operation, reconnecting with exponential backoff on network errors.

    The operation itself owns no connection lifecycle. A failed connection is closed,
    a new authenticated connection is opened, and the same operation is called again.
    For downloads this works with ``.part`` resume handling in ``download_remote_file``.
    """
    if retries < 0:
        raise ValueError("retries must be zero or greater")
    if base_delay_seconds < 0 or max_delay_seconds < 0:
        raise ValueError("retry delays must be zero or greater")

    current = ftp
    for failure_count in range(retries + 1):
        try:
            if current is None:
                current = connect(config)
            return operation(current), current
        except Exception as exc:
            if not is_retryable_ftp_error(exc):
                raise
            close_ftp_quietly(current)
            current = None
            if failure_count >= retries:
                raise
            retry_number = failure_count + 1
            delay = min(
                max_delay_seconds,
                base_delay_seconds * (2**failure_count),
            )
            if on_retry is not None:
                on_retry(retry_number, retries, delay, exc)
            sleep(delay)

    raise AssertionError("unreachable")
