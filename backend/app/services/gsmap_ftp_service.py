"""Read-only FTP retrieval for JAXA GSMaP rainfall products."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from ftplib import FTP, FTP_TLS, error_perm
import hashlib
import json
import os
from pathlib import Path
import posixpath
import re
from typing import Any, Iterator


@dataclass(frozen=True)
class GsmapDatasetSpec:
    """FTP subdirectory and filename prefix for a GSMaP dataset."""

    remote_subdir: str
    filename_prefix: str


DATASET_SPECS: dict[str, GsmapDatasetSpec] = {
    "hourly": GsmapDatasetSpec("hourly", "gsmap_mvk"),
    "hourly-gauge": GsmapDatasetSpec("hourly_G", "gsmap_gauge"),
}


@dataclass(frozen=True)
class GsmapFtpConfig:
    host: str
    port: int
    username: str
    password: str
    use_tls: bool = False
    passive: bool = True
    timeout_seconds: float = 60.0


@dataclass(frozen=True)
class GsmapRemoteFile:
    remote_path: str
    file_name: str
    observation_date: date
    size: int | None = None
    modified_at: datetime | None = None


@dataclass(frozen=True)
class GsmapDownloadResult:
    status: str
    remote_path: str
    local_path: Path
    size: int
    sha256: str | None
    modified_at: datetime | None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["local_path"] = str(self.local_path.resolve())
        data["modified_at"] = (
            self.modified_at.isoformat() if self.modified_at else None
        )
        return data


def normalize_product_path(product: str) -> str:
    """Return a safe relative FTP product path such as ``standard/v8``."""
    normalized = product.strip().replace("\\", "/").strip("/")
    parts = normalized.split("/") if normalized else []
    if not parts or any(
        part in {"", ".", ".."}
        or not re.fullmatch(r"[A-Za-z0-9._-]+", part)
        for part in parts
    ):
        raise ValueError(f"Invalid GSMaP product path: {product!r}")
    return "/".join(parts)


def parse_date_argument(value: str, *, today: date | None = None) -> date:
    """Parse ISO date text, accepting ``today`` in UTC."""
    if value.strip().lower() == "today":
        return today or datetime.now(timezone.utc).date()
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid date {value!r}; expected YYYY-MM-DD or today") from exc


def iter_dates(start_date: date, end_date: date) -> Iterator[date]:
    if end_date < start_date:
        raise ValueError("end date must be on or after start date")
    current = start_date
    while current <= end_date:
        yield current
        current = date.fromordinal(current.toordinal() + 1)


def build_remote_directory(
    product: str,
    dataset: str,
    target_date: date,
) -> str:
    spec = DATASET_SPECS[dataset]
    return posixpath.join(
        "/",
        normalize_product_path(product),
        spec.remote_subdir,
        target_date.strftime("%Y"),
        target_date.strftime("%m"),
        target_date.strftime("%d"),
    )


def is_matching_hourly_file(
    file_name: str,
    dataset: str,
    target_date: date,
) -> bool:
    spec = DATASET_SPECS[dataset]
    prefix = re.escape(spec.filename_prefix)
    day = target_date.strftime("%Y%m%d")
    pattern = re.compile(
        rf"^{prefix}\.{day}\.(?:[01]\d|2[0-3])00\.v\d+\.\d+\.\d+\.dat(?:\.gz)?$",
        re.IGNORECASE,
    )
    return pattern.fullmatch(Path(file_name).name) is not None


def open_ftp(config: GsmapFtpConfig) -> FTP:
    """Connect and authenticate without issuing any remote write command."""
    ftp: FTP
    if config.use_tls:
        tls_ftp = FTP_TLS(timeout=config.timeout_seconds)
        ftp = tls_ftp
    else:
        ftp = FTP(timeout=config.timeout_seconds)

    ftp.connect(config.host, config.port, timeout=config.timeout_seconds)
    ftp.login(config.username, config.password)
    ftp.set_pasv(config.passive)
    if isinstance(ftp, FTP_TLS):
        ftp.prot_p()
    return ftp


def _parse_ftp_modified(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.split(".", 1)[0]
    try:
        return datetime.strptime(raw, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _is_missing_path(exc: error_perm) -> bool:
    return str(exc).startswith("550")


def _is_mlsd_unsupported(exc: error_perm) -> bool:
    return str(exc).startswith(("500", "501", "502", "504"))


def list_remote_files(
    ftp: FTP,
    *,
    product: str,
    dataset: str,
    target_date: date,
) -> list[GsmapRemoteFile]:
    """List matching files using MLSD, falling back to NLST for older servers."""
    remote_dir = build_remote_directory(product, dataset, target_date)
    entries: list[GsmapRemoteFile] = []

    try:
        for name, facts in ftp.mlsd(remote_dir, facts=["type", "size", "modify"]):
            if facts.get("type") != "file" or not is_matching_hourly_file(
                name, dataset, target_date
            ):
                continue
            size_text = facts.get("size")
            entries.append(
                GsmapRemoteFile(
                    remote_path=posixpath.join(remote_dir, name),
                    file_name=Path(name).name,
                    observation_date=target_date,
                    size=int(size_text) if size_text and size_text.isdigit() else None,
                    modified_at=_parse_ftp_modified(facts.get("modify")),
                )
            )
        return sorted(entries, key=lambda item: item.file_name)
    except error_perm as exc:
        if _is_missing_path(exc):
            return []
        if not _is_mlsd_unsupported(exc):
            raise

    try:
        names = ftp.nlst(remote_dir)
    except error_perm as exc:
        if _is_missing_path(exc):
            return []
        raise

    for listed_name in names:
        file_name = posixpath.basename(listed_name.rstrip("/"))
        if not is_matching_hourly_file(file_name, dataset, target_date):
            continue
        remote_path = (
            listed_name
            if listed_name.startswith("/")
            else posixpath.join(remote_dir, file_name)
        )
        size: int | None = None
        modified_at: datetime | None = None
        try:
            size = ftp.size(remote_path)
        except error_perm:
            pass
        try:
            response = ftp.sendcmd(f"MDTM {remote_path}")
            modified_at = _parse_ftp_modified(response.removeprefix("213 ").strip())
        except error_perm:
            pass
        entries.append(
            GsmapRemoteFile(
                remote_path=remote_path,
                file_name=file_name,
                observation_date=target_date,
                size=size,
                modified_at=modified_at,
            )
        )
    return sorted(entries, key=lambda item: item.file_name)


def iter_remote_files(
    ftp: FTP,
    *,
    product: str,
    dataset: str,
    start_date: date,
    end_date: date,
) -> Iterator[GsmapRemoteFile]:
    for target_date in iter_dates(start_date, end_date):
        yield from list_remote_files(
            ftp,
            product=product,
            dataset=dataset,
            target_date=target_date,
        )


def build_local_path(
    output_root: Path,
    product: str,
    dataset: str,
    remote_file: GsmapRemoteFile,
) -> Path:
    return (
        output_root
        / Path(*normalize_product_path(product).split("/"))
        / dataset
        / remote_file.observation_date.strftime("%Y")
        / remote_file.observation_date.strftime("%m")
        / remote_file.observation_date.strftime("%d")
        / remote_file.file_name
    )


def calculate_sha256(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def download_remote_file(
    ftp: FTP,
    *,
    remote_file: GsmapRemoteFile,
    destination: Path,
    resume: bool = True,
    chunk_size: int = 1024 * 1024,
) -> GsmapDownloadResult:
    """Download with RETR into a local partial file, then finalize atomically."""
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.is_file():
        local_size = destination.stat().st_size
        if remote_file.size is None or local_size == remote_file.size:
            return GsmapDownloadResult(
                status="skipped",
                remote_path=remote_file.remote_path,
                local_path=destination,
                size=local_size,
                sha256=None,
                modified_at=remote_file.modified_at,
            )
        raise FileExistsError(
            f"Existing local file has a different size: {destination} "
            f"(local={local_size}, remote={remote_file.size})"
        )

    partial_path = destination.with_name(destination.name + ".part")
    offset = partial_path.stat().st_size if resume and partial_path.is_file() else 0
    if remote_file.size is not None and offset > remote_file.size:
        partial_path.unlink()
        offset = 0

    def retrieve(*, append: bool, rest: int | None) -> None:
        mode = "ab" if append else "wb"
        with partial_path.open(mode) as stream:
            ftp.retrbinary(
                f"RETR {remote_file.remote_path}",
                stream.write,
                blocksize=chunk_size,
                rest=rest,
            )

    if offset:
        try:
            retrieve(append=True, rest=offset)
        except error_perm as exc:
            if not str(exc).startswith(("500", "501", "502", "504")):
                raise
            retrieve(append=False, rest=None)
    else:
        retrieve(append=False, rest=None)

    downloaded_size = partial_path.stat().st_size
    if remote_file.size is not None and downloaded_size != remote_file.size:
        raise IOError(
            f"Downloaded size mismatch for {remote_file.remote_path}: "
            f"local={downloaded_size}, remote={remote_file.size}"
        )

    sha256 = calculate_sha256(partial_path)
    os.replace(partial_path, destination)
    if remote_file.modified_at:
        timestamp = remote_file.modified_at.timestamp()
        os.utime(destination, (timestamp, timestamp))

    return GsmapDownloadResult(
        status="downloaded",
        remote_path=remote_file.remote_path,
        local_path=destination,
        size=downloaded_size,
        sha256=sha256,
        modified_at=remote_file.modified_at,
    )


def append_manifest(path: Path, result: GsmapDownloadResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        **result.to_dict(),
    }
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
